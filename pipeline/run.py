"""수집 → 계산 → data.json 이 바뀌었으면 커밋·푸시. LaunchAgent 가 이걸 부른다.
launchd 는 ~/Downloads 의 bash 를 TCC 로 막으므로 셸 스크립트 대신 venv 파이썬으로 실행한다.
"""
import datetime as dt
import os
import subprocess
import sys

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(H)
sys.path.insert(0, H)


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)


def main():
    print("──", dt.datetime.now().strftime("%Y-%m-%d %H:%M"), flush=True)
    import fetch
    import build
    try:
        fetch.main()
    except Exception as e:  # 수집 일부 실패해도 있는 데이터로 계산은 한다
        print("fetch 실패:", repr(e), flush=True)
    build.main()
    if "--push" not in sys.argv:
        return
    git("add", "docs/data.json")
    if git("diff", "--cached", "--quiet").returncode == 0:
        print("변경 없음"); return
    c = git("commit", "-m", f"data: {dt.datetime.now():%Y-%m-%d %H:%M} 갱신")
    p = git("push", "-q", "origin", "HEAD")
    print("push", "ok" if p.returncode == 0 else p.stderr.strip() or c.stderr.strip())


if __name__ == "__main__":
    main()
