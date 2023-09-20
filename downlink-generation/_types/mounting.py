from enum import IntEnum


class MountingTypes(IntEnum):
    def __new__(cls, value: int, phrase: str, description: str):
        obj = int.__new__(cls, value)
        obj._value_ = value

        obj.phrase = phrase
        obj.description = description
        return obj

    PBS = (0, "PBS", "pressure-bearing-screw")
    ADP = (1, "ADP", "adapter")
    RFC = (2, "RFC", "retro-fit-clamp")

    @staticmethod
    def get_member_by_phrase(_phrase: str, /) -> int:
        _phrase = _phrase.strip()
        for member in MountingTypes:
            if member.phrase == _phrase:
                return member
        else:
            raise KeyError(f"There is no member with such phrase.")
