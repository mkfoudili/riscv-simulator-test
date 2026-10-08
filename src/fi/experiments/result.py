from enum import Enum


class Result(Enum):
    NO_EFFECT = "no_effect"
    SILENT_DATA_CORRUPTION = "silent_data_corruption"
    HANG_CRASH = "hang_crash"

    @property
    def label(self) -> str:
        if self is Result.NO_EFFECT:
            return "No effect"
        if self is Result.HANG_CRASH:
            return "Hang/crash"
        return "Silent data corruption"

    def __str__(self) -> str:
        return self.label


class ResultClassifier:
    @staticmethod
    def classify(correct_output: int, faulty_output: int) -> Result:
        return (
            Result.NO_EFFECT
            if faulty_output == correct_output
            else Result.SILENT_DATA_CORRUPTION
        )