"""Optional notifications. Telegram is used only when TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set;
GitHub issues are created with the same token that runs the workflow. Failures never break the run."""
import json, os, urllib.request


def telegram(text):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return False
    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", method="POST",
                                     data=json.dumps({"chat_id": chat, "text": text[:3900],
                                                      "disable_web_page_preview": True}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=20).read()
        return True
    except Exception as e:
        print("telegram failed:", type(e).__name__)
        return False


def issue(repo, title, body, labels=("alert",)):
    tok = os.environ.get("GH_PAT")
    if not tok:
        return False
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues", method="POST",
                                     data=json.dumps({"title": title, "body": body, "labels": list(labels)}).encode(),
                                     headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
                                              "Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30).read()
        return True
    except Exception as e:
        print("issue failed:", type(e).__name__)
        return False


if __name__ == "__main__":  # python -m ghintel.notify "message"
    import sys
    print("sent" if telegram(" ".join(sys.argv[1:])) else "not configured")
