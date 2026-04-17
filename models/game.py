from config import FATE_LINE_LENGTH
from utils.gm_utils import get_team
from typing import List

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
        self.players : List[PlayerState] = []
        self.fate_points = 0
        self.fate_line = FATE_LINE_LENGTH
        self.round = None
        self.log = []