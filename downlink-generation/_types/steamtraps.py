from enum import IntEnum


class SteamTrapTypes(IntEnum):
    def __new__(cls, value: int, phrase: str, description: str):
        obj = int.__new__(cls, value)
        obj._value_ = value

        obj.phrase = phrase
        obj.description = description
        return obj

    BK = (0, "BK", "bimetallic")
    MK = (1, "MK", "membrane")
    UNA = (2, "UNA", "ball-float")

    @staticmethod
    def get_member_by_description(_description: str, /) -> int:
        _description = _description.strip()
        for member in SteamTrapTypes:
            if member.description == _description:
                return member
        else:
            raise KeyError(f"There is no member with such description.")
