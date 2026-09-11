from zxcvbn import zxcvbn

from models.schemas import PasswordCheckResponse


def check_password_strength(password: str) -> PasswordCheckResponse:
    result = zxcvbn(password)
    feedback = result["feedback"].get("warning") or next(
        iter(result["feedback"].get("suggestions", [])), ""
    )
    if not feedback:
        feedback = "Strong password" if result["score"] >= 3 else "Weak password"

    return PasswordCheckResponse(
        score=result["score"],
        feedback=feedback,
        crack_time_display=str(
            result["crack_times_display"]["offline_slow_hashing_1e4_per_second"]
        ),
    )
