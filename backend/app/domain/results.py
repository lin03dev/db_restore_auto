from typing import Any, Dict


def success_result(**extra: Any) -> Dict[str, Any]:
    return {"success": True, **extra}


def failure_result(error_code: str, message: str, **extra: Any) -> Dict[str, Any]:
    return {"success": False, "error_code": error_code, "message": message, **extra}


def summarize_details(details: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    if not details:
        return {
            "success": False,
            "partial": False,
            "succeeded": [],
            "failed": [],
            "skipped": [],
        }

    succeeded = [
        name
        for name, item in details.items()
        if item.get("success") and not item.get("skipped")
    ]
    failed = [
        name
        for name, item in details.items()
        if not item.get("success") and not item.get("skipped")
    ]
    skipped = [name for name, item in details.items() if item.get("skipped")]

    if succeeded and failed:
        partial = True
        success = True
    elif succeeded:
        partial = False
        success = True
    elif skipped and failed:
        partial = True
        success = True
    elif skipped:
        partial = False
        success = True
    else:
        partial = False
        success = False

    return {
        "success": success,
        "partial": partial,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
    }
