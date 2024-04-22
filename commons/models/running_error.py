class RunningErrorCalculator:
    # Type declarations
    total_error: float
    running_count: int

    def __init__(self, total_error: float = 0.0, running_count: int = 0):
        self.total_error = total_error
        self.running_count = running_count

    def update(self, expected_rotation: int, actual_rotation: int) -> int:
        error: int = abs(expected_rotation - actual_rotation) % 180
        error: int = min(error, 180 - error)
        self.total_error += error
        self.running_count += 1
        return error

    def get_average(self) -> float:
        if self.running_count <= 0:
            raise ValueError("No errors have been recorded")
        return self.total_error / self.running_count

    def merge(self, other: "RunningErrorCalculator") -> None:
        self.total_error += other.total_error
        self.running_count += other.running_count

    def __str__(self) -> str:
        return f"{self.get_average()} ({int(self.total_error)}/{self.running_count})"


if __name__ == "__main__":
    # Test the running error calculator a little
    calculator = RunningErrorCalculator()
    calculator.update(0, 10)
    assert calculator.get_average() == 10
    calculator.update(0, 40)
    assert calculator.get_average() == 25

    calculator2 = RunningErrorCalculator(75, 2)
    calculator.merge(calculator2)
    assert calculator.total_error == 125
    assert calculator.running_count == 4
    assert calculator.get_average() == 31.25

    calculator.update(0, 0)
    assert calculator.get_average() == 25
