from dataclasses import dataclass

from . import rules
from .rules import Move
from .state import Card, State


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    state: State
    message: str = ''
    move: Move | None = None
    game_won: bool = False


def serialize_card(card):
    if card is None:
        return None
    return {'rank': card.rank, 'suit': card.suit, 'color': card.color, 'label': repr(card)}


def serialize_move(move):
    return {
        'src_type': move.src_type,
        'src_index': move.src_index,
        'dst_type': move.dst_type,
        'dst_index': move.dst_index,
        'count': move.count,
    }


def serialize_state(state):
    return {
        'cascades': [[serialize_card(card) for card in cascade] for cascade in state.cascades],
        'free_cells': [serialize_card(card) for card in state.free_cells],
        'foundations': state.foundations.copy(),
        'is_goal': rules.is_goal(state),
        'legal_moves': [serialize_move(move) for move in rules.enumerate_legal_moves(state)],
    }


class FreeCellGame:
    def __init__(self, seed=None, state=None):
        if state is not None and seed is not None:
            raise ValueError("Provide either seed or state, not both")
        if state is not None:
            self.state = state
        else:
            self.state = State.microsoft_shuffle(1 if seed is None else seed)

    def new_game(self, seed=None):
        self.state = State.microsoft_shuffle(1 if seed is None else seed)
        return self.get_view_model()

    def set_state(self, state):
        self.state = state

    def get_state(self):
        return self.state

    def get_view_model(self):
        return serialize_state(self.state)

    def get_legal_moves(self):
        return rules.enumerate_legal_moves(self.state)

    def get_legal_move_payloads(self):
        return [serialize_move(move) for move in self.get_legal_moves()]

    def try_move(self, src_type, src_index, dst_type, dst_index, count=1):
        move = Move(src_type, src_index, dst_type, dst_index, count=count)
        if not rules.is_legal_move(self.state, move):
            return ActionResult(
                ok=False,
                state=self.state,
                message='Illegal move',
                move=move,
                game_won=rules.is_goal(self.state),
            )

        self.state = rules.apply_move(self.state, move)
        return ActionResult(
            ok=True,
            state=self.state,
            message='Move applied',
            move=move,
            game_won=rules.is_goal(self.state),
        )

    def auto_move_to_foundation(self):
        for move in self.get_legal_moves():
            if move.dst_type == rules.LOCATION_FOUNDATION:
                self.state = rules.apply_move(self.state, move)
                return ActionResult(
                    ok=True,
                    state=self.state,
                    message='Auto-moved card to foundation',
                    move=move,
                    game_won=rules.is_goal(self.state),
                )

        return ActionResult(
            ok=False,
            state=self.state,
            message='No foundation move available',
            move=None,
            game_won=rules.is_goal(self.state),
        )
