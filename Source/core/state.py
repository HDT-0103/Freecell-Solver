import copy

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.color = 'red' if suit in ['H', 'D'] else 'black'

    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self):
        return hash((self.rank, self.suit))

    def __repr__(self):
        ranks = {1: 'A', 11: 'J', 12: 'Q', 13: 'K'}
        r = ranks.get(self.rank, str(self.rank))
        return f"{r}{self.suit}"
        
class State:
    def __init__(self, cascades, free_cells=None, foundations=None, parent=None, move=None):
        self.cascades = [list(c) for c in cascades]
        self.free_cells = list(free_cells) if free_cells is not None else [None] * 4
        self.foundations = foundations.copy() if foundations is not None else {'H': 0, 'D': 0, 'C': 0, 'S': 0}

        self.parent = parent
        self.move = move
        self.g = parent.g + 1 if parent else 0 
        self.h = 0

    def __repr__ (self):
        res = f"FreeCells: {self.free_cells} | Foundations: {self.foundations} \n"
        res += "Cascades:\n"
        for i, col in enumerate(self.cascades):
            res += f" {i} : {col}\n"
        return res

    def __eq__(self, other):
        if not isinstance(other, State):
            return False
        return (self.cascades == other.cascades) and (self.free_cells == other.free_cells) and (self.foundations == other.foundations)
    
    @staticmethod
    def microsoft_shuffle(seed):
        cards = []
        for suit in ['C','D','H','S']:
            for rank in range(1,14):
                cards.append(Card(rank,suit))

        res = []
        state = seed
        def ms_rand():
            nonlocal state
            state = (state * 214013 + 2531011) & 0x7FFFFFFF
            return (state >> 16) & 0x7FFF
        # Shuffle from end to beginning
        cards_left = 52
        while cards_left > 0:
            j = ms_rand() % cards_left
            res.append(cards.pop(j))
            cards_left -= 1
        
        #Divide into 8 cascades
        res.reverse()
        cascades = [[] for _ in range(8)]
        for i, card in enumerate(res):
                cascades[i%8].append(card)
        return State(cascades)
    
    def get_max_move_size(self, moving_to_empty_stack=False):
        """Calculate the maximum number of cards that can be moved based on the empty space. """
        empty_free_cells = self.free_cells.count(None)
        empty_cascades = sum(1 for c in self.cascades if not c)
        if moving_to_empty_stack:
            empty_cascades -= 1 # Cột đích trống không tính vào multiplier
        return (1 + empty_free_cells) * (2 ** max(0, empty_cascades))

    def _move(self, src, dst):
        """Di chuyển 1 lá bài đơn lẻ"""
        new_state = State([c[:] for c in self.cascades], self.free_cells[:], self.foundations.copy(), parent=self)
        # Pop card
        type_s, idx_s = src
        card = new_state.cascades[idx_s].pop() if type_s == 'cascade' else new_state.free_cells[idx_s]
        if type_s == 'free_cell': new_state.free_cells[idx_s] = None
        # Push card
        type_d, idx_d = dst
        if type_d == 'foundation': new_state.foundations[idx_d] += 1
        elif type_d == 'free_cell': new_state.free_cells[idx_d] = card
        elif type_d == 'cascade': new_state.cascades[idx_d].append(card)
        return new_state
    
    def _move_seq(self, src_idx, dst_idx, length):
        """Di chuyển một chuỗi bài"""
        new_state = State([c[:] for c in self.cascades], self.free_cells[:], self.foundations.copy(), parent=self)
        seq = new_state.cascades[src_idx][-length:]
        new_state.cascades[src_idx] = new_state.cascades[src_idx][:-length]
        new_state.cascades[dst_idx].extend(seq)
        return new_state
    
    def is_goal(self):
        """Check if all 52 cards were in the foundations"""
        return sum(self.foundations.values()) == 52
    
    def __lt__(self, other):
        """Compare the cost of 2 nodes"""
        return (self.g + self.h) < (other.g + other.h)
    
    def get_hash(self):
        return hash((
        tuple(tuple(c) for c in self.cascades),
        tuple(self.free_cells),
        tuple(sorted(self.foundations.items()))
    ))

    def get_next_states(self):
        next_states = []
        
        # --- LUẬT 1: DI CHUYỂN VÀO FOUNDATION (Ưu tiên cao nhất)---
        # Kiểm tra từ Cascades
        for i, col in enumerate(self.cascades):
            if col:
                card = col[-1]
                if card.rank == self.foundations[card.suit] + 1:
                    next_states.append(self._move(src=('cascade', i), dst=('foundation', card.suit)))
        # Kiểm tra từ Free Cells
        for i, card in enumerate(self.free_cells):
            if card and card.rank == self.foundations[card.suit] + 1:
                next_states.append(self._move(src=('free_cell', i), dst=('foundation', card.suit)))

        # --- LUẬT 2: DI CHUYỂN CHUỖI BÀI (SEQUENCES) GIỮA CÁC CASCADES  ---
        for i, src_col in enumerate(self.cascades):
            if not src_col: continue
            
            # Tìm các chuỗi con hợp lệ ở cuối cột
            for seq_len in range(1, len(src_col) + 1):
                sub_seq = src_col[-seq_len:]
                # Kiểm tra chuỗi hợp lệ (Giảm dần & xen kẽ màu)
                is_valid_seq = True
                for k in range(len(sub_seq) - 1):
                    if not (sub_seq[k].color != sub_seq[k+1].color and sub_seq[k].rank == sub_seq[k+1].rank + 1):
                        is_valid_seq = False
                        break
                if not is_valid_seq: continue

                # Thử di chuyển chuỗi này sang các cột khác
                for j, dst_col in enumerate(self.cascades):
                    if i == j: continue
                    
                    max_size = self.get_max_move_size(moving_to_empty_stack=(not dst_col))
                    if seq_len > max_size: continue

                    if not dst_col: # Cột đích trống
                        next_states.append(self._move_seq(i, j, seq_len))
                    else: # Cột đích có bài, kiểm tra lá trên cùng
                        top_card = dst_col[-1]
                        bottom_seq_card = sub_seq[0]
                        if bottom_seq_card.color != top_card.color and bottom_seq_card.rank == top_card.rank - 1:
                            next_states.append(self._move_seq(i, j, seq_len))

        # --- LUẬT 3: DI CHUYỂN VÀO FREE CELL ---
        empty_fc_idx = next((idx for idx, val in enumerate(self.free_cells) if val is None), None)
        if empty_fc_idx is not None:
            for i, col in enumerate(self.cascades):
                if col:
                    next_states.append(self._move(src=('cascade', i), dst=('free_cell', empty_fc_idx)))

        return next_states
    
    

        

    
