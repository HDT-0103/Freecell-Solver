"""
adapter.py
---------
Adapter để chuyển đổi giữa State (core mới) và GameState (GUI cũ) cho việc compatibility.
"""
from typing import Optional, List
from core.state import Card, State, CardData, GameState

def state_to_gamestate(state: State) -> GameState:
    """Convert from new State to old GameState for backward compatibility."""
    # Map Card to CardData
    cascades = []
    for cascade in state.cascades:
        cascade_data = []
        for card in cascade:
            cascade_data.append(CardData(rank=card.rank, suit=_suit_short_to_long(card.suit)))
        cascades.append(cascade_data)
    
    # Map free_cells
    free_cells = []
    for card in state.free_cells:
        if card is None:
            free_cells.append(None)
        else:
            free_cells.append(CardData(rank=card.rank, suit=_suit_short_to_long(card.suit)))
    
    # Map foundations
    suit_names = {"H": "hearts", "D": "diamonds", "C": "clubs", "S": "spades"}
    foundations = [[], [], [], []]
    for suit, rank in state.foundations.items():
        idx = {"C": 0, "D": 1, "H": 2, "S": 3}[suit]
        suit_long = suit_names[suit]
        for r in range(1, rank + 1):
            foundations[idx].append(CardData(rank=r, suit=suit_long))
    
    gs = GameState(cascades=cascades, free_cells=free_cells, foundations=foundations)
    return gs

def gamestate_to_state(game_state: GameState) -> State:
    """Convert from old GameState to new State."""
    suit_map = {"clubs": "C", "diamonds": "D", "hearts": "H", "spades": "S"}
    
    # Map cascades
    cascades = []
    for cascade_data in game_state.cascades:
        cascade = []
        for card_data in cascade_data:
            cascade.append(Card(rank=card_data.rank, suit=suit_map[card_data.suit]))
        cascades.append(cascade)
    
    # Map free_cells
    free_cells = []
    for card_data in game_state.free_cells:
        if card_data is None:
            free_cells.append(None)
        else:
            free_cells.append(Card(rank=card_data.rank, suit=suit_map[card_data.suit]))
    
    # Map foundations
    foundations = {suit: 0 for suit in ["C", "D", "H", "S"]}
    for i, pile in enumerate(game_state.foundations):
        suit_abbr = ["C", "D", "H", "S"][i]
        foundations[suit_abbr] = len(pile)
    
    return State(cascades=cascades, free_cells=free_cells, foundations=foundations)

def _suit_short_to_long(suit: str) -> str:
    """Convert H/D/C/S to hearts/diamonds/clubs/spades."""
    suit_map = {"H": "hearts", "D": "diamonds", "C": "clubs", "S": "spades"}
    return suit_map.get(suit, suit)
