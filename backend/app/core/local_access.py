from fastapi import HTTPException, Request, status

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def require_local_access(request: Request) -> None:
    if request.url.hostname not in LOCAL_HOSTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The admin interface is available only from this computer",
        )
