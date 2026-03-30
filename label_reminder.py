import os
import requests

# ── Ortam değişkenleri (GitHub Secrets'tan gelecek) ──────────────────────────
JIRA_BASE_URL = "https://invent.atlassian.net"
JIRA_EMAIL    = os.environ["JIRA_EMAIL"]        # örn: sen@invent.ai
JIRA_TOKEN    = os.environ["JIRA_API_TOKEN"]    # Jira API token
SLACK_TOKEN   = os.environ["SLACK_BOT_TOKEN"]   # Slack Bot token
SLACK_CHANNEL = "C042Y0WG36J"                   # #team_mdn_cx

# ── Jira email → Slack user ID eşlemesi ──────────────────────────────────────
# Yeni kişi eklenirse buraya ekle
EMAIL_TO_SLACK = {
    "leyli.jafarova@invent.ai" : "U023F3E4LRF",
    "caner.gunduz@invent.ai"   : "U07ELV7J5F1",
    "ada.haholu@invent.ai"     : "U07L2TANFCP",
    "ece.yurtsever@invent.ai"  : "U084A61BF52",
    "ecem.sert@invent.ai"      : "U087B6YQPNE",
    "ugur.kilinc@invent.ai"    : "U01EQ4NM0UV",
}

# ── JQL sorgusu ───────────────────────────────────────────────────────────────
JQL = """
labels IS EMPTY
AND project IN ("TCS","LP2CS","ATCS","APRLTRN","IPEKYOLMD","MMCS")
AND issuetype IN (
    "Service/Operational Work Log","Int Call","Reporting","Analysis",
    "Client Call","Bug",Documentation,Development,Handover,Task,
    Extension,"Fault (Off-Duty)","Version Upgrade","Product Test","R&D"
)
AND (created >= "-180d" OR updated >= "-180d")
AND timespent > 0
ORDER BY created ASC, status ASC, assignee ASC
""".strip()

# ── Jira'dan taskları çek ─────────────────────────────────────────────────────
def fetch_issues():
    # Jira, GET /search endpoint'ini deprecated etti → POST /search/jql kullan
    url = f"{JIRA_BASE_URL}/rest/api/3/search/jql"
    auth = (JIRA_EMAIL, JIRA_TOKEN)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    issues = []
    start = 0

    while True:
        payload = {
            "jql": JQL,
            "startAt": start,
            "maxResults": 100,
            "fields": ["summary", "assignee", "status", "labels"]
        }
        resp = requests.post(url, auth=auth, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("issues", [])
        issues.extend(batch)
        if start + len(batch) >= data["total"]:
            break
        start += len(batch)

    return issues

# ── Slack'e mesaj gönder ──────────────────────────────────────────────────────
def send_slack(text):
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_TOKEN}"},
        json={"channel": SLACK_CHANNEL, "text": text}
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"Slack hatası: {result.get('error')}")

# ── Ana akış ─────────────────────────────────────────────────────────────────
def main():
    issues = fetch_issues()

    if not issues:
        print("Labelsız task bulunamadı, mesaj gönderilmedi.")
        return

    lines = []
    for issue in issues:
        key        = issue["key"]
        fields     = issue["fields"]
        status     = fields["status"]["statusCategory"]["key"]  # "done" veya diğerleri
        assignee   = fields.get("assignee")
        issue_url  = f"{JIRA_BASE_URL}/browse/{key}"
        issue_link = f"<{issue_url}|{key}>"

        if assignee:
            email    = assignee.get("emailAddress", "")
            slack_id = EMAIL_TO_SLACK.get(email)
            mention  = f"<@{slack_id}>" if slack_id else assignee.get("displayName", "?")
        else:
            mention = "_(atanmamış)_"

        if status == "done":
            line = f"{mention} {issue_link} taskını kapatmışsın üstelik label'sız halde oh ne güzel hayat! 🎉"
        else:
            line = f"{mention} sana atanmış {issue_link} taskının label'ını düzeltmeyi unutma 🏷️"

        lines.append(line)

    message = "\n".join(lines)
    send_slack(message)
    print(f"✅ {len(lines)} task için Slack mesajı gönderildi.")

if __name__ == "__main__":
    main()
