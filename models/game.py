from config import FATE_LINE_LENGTH
from utils.gm_utils import get_team
from typing import List


class NumberCardState:
    # hold number card data

    def __init__(self):
        self._type = "number"  # immutable
        self._number = None  # only between 5 and 0
        self._label = None  # bound to string
        self._choice = False  # default false

    #region Multiple setters and getters via properties to trigger immutability or control type
    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, value):
        # immutable, pass it
        pass

    @property
    def number(self):
        return self._number

    @number.setter
    def number(self, value):
        if not isinstance(value, int):
            raise ValueError("Invalid type for number")
        if value < 0 or value > 5:
            raise ValueError("Invalid number for number")

        self._number = value

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, value):
        if not isinstance(value, str):
            raise ValueError("Invalid type for label")
        self._label = value

    @property
    def choice(self):
        return self._choice

    @choice.setter
    def choice(self, value):
        if not isinstance(value, bool):
            raise ValueError("Invalid type for choice")
        self._choice = value
    #endregion


class SpecialCardState:
    def __init__(self):
        self._type = "special"
        self._action = None
        self._label = None

    #region Getters and setters for special card
    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, value):
        # immutable, pass it
        pass

    @property
    def action(self):
        return self._action

    @action.setter
    def action(self, value):
        if not isinstance(value, str):
            raise ValueError("Invalid type for action")
        self._action = value

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, value):
        if not isinstance(value, str):
            raise ValueError("Invalid type for label")
        self._label = value
    #endregion

class PlayerState:
    def __init__(self):
        self.name = None
        self._role = None  # this mutates _team
        self._team = None  # this is never mutated directly
        self._hand = []  # mutates _card_count
        self._card_count = 0  # never mutates directly
        self.sid = None

    #region Getters and setters and disabling certain values mutability
    @property
    def role(self):
        return self._role

    @role.setter
    def role(self, r):
        self._role = r
        self._team = get_team(r)

    @property
    def team(self):
        return self._team

    @team.setter
    def team(self, value):
        pass  # this will never be called, team cannot be mutated directly

    @property
    def hand(self):
        return self._hand

    @hand.setter
    def hand(self, value):
        self._hand = value
        self._card_count = len(value)

    @property
    def card_count(self):
        return self._card_count

    @card_count.setter
    def card_count(self, value):
        pass  # card count will never be mutated
    #endregion


# TODO: Complete Game State and implement
class GameState:
    def __init__(self):
        self.running_total = None
        self.current_player_idx = 0
        self.direction = 1
        self.players: List[PlayerState] = []
        self.fate_points = 0
        self.fate_line = FATE_LINE_LENGTH
        self.round = None
        self.log = []
