def get_current_user(token: str = ""):
    if token != "secret":
        raise Exception("没权限")
    return {"user": "dachao"}
