ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$6jy3oGhWeTkcPgnk$24daa97b98a863051d0872bd197a897a1db1cdff410d3ea08381994a29c463d7e320548f5546ff3da6de41e779e02635762afa946f7fc4962a5feae6aef6e668"

ROLES = ["Oracle", "Ogre", "Witch", "Werewolf", "Queen", "Jester", "Knight", "Horse"]
MAX_PLAYERS = len(ROLES)

COURTS = ["Queen", "Jester", "Knight", "Horse"]
MONSTERS = ["Oracle", "Ogre", "Witch", "Werewolf"]
BLOCKABLE_ACTIONS = {"plus1", "plus2", "skip", "counterturn", "barter"}

FATE_LINE_LENGTH = 5

SECRET_KEY = "youngenterprise"