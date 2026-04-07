import os
import requests

# ── Ortam değişkenleri (GitHub Secrets'tan gelecek) ──────────────────────────
JIRA_BASE_URL = "https://invent.atlassian.net"
JIRA_EMAIL    = os.environ["JIRA_EMAIL"]
JIRA_TOKEN    = os.environ["JIRA_API_TOKEN"]
SLACK_TOKEN   = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL = "C042Y0WG36J"  # #team_mdn_cx

# ── Jira email → Slack user ID eşlemesi ──────────────────────────────────────
# Yeni kişi eklenirse buraya ekle
EMAIL_TO_SLACK = {
    "leyli.jafarova@invent.ai" : "U023F3E4LRF",
    "caner.gunduz@invent.ai"   : "U07ELV7J5F1",
    "ada.haholu@invent.ai"     : "U07L2TANFCP",
    "ece.yurtsever@invent.ai"  : "U084A61BF52",
    "ecem.sert@invent.ai"      : "U087B6YQPNE",
    "ugur.kilinc@invent.ai"    : "U01EQ4NM0UV",
    "ata.tosun@invent.ai"      : "D09EQ8JRCMP"
}

# ── JQL sorguları ─────────────────────────────────────────────────────────────

# Query 1: Label'sız tasklar
JQL_NO_LABEL = 'labels IS EMPTY AND project IN ("TCS","LP2CS","ATCS","APRLTRN","IPEKYOLMD","MMCS") AND issuetype IN ("Service/Operational Work Log","Int Call","Reporting","Analysis","Client Call","Bug","Documentation","Development","Handover","Task","Extension","Fault (Off-Duty)","Version Upgrade","Product Test","R&D") AND (created >= "-180d" OR updated >= "-180d") ORDER BY created ASC, status ASC, assignee ASC'

# Query 2: Related Project alanı boş
JQL_NO_RELATED_PROJECT = 'project in ("TCS","LP2CS","FLOMCS","FMCS","ATCS","APRLTRN","IPEKYOLMD","MMCS") AND (created >= "-180d" OR updated >= "-180d") AND "Related Project[Project Picker (single project)]" IS EMPTY ORDER BY created DESC'

# Query 3: Issue type ile uyumsuz label
JQL_WRONG_LABEL = 'project in ("TCS","LP2CS","ATCS","APRLTRN","IPEKYOLMD","MMCS") AND (created >= "-180d" OR updated >= "-180d") AND ((type = "Service/Operational Work Log" AND labels NOT IN ("ETL","OperationalRequest","ProcessFollowups","Parameter/Configuration","RunReview","RunTrigger","RunError","Dagfails","Maintenance")) OR (type = Development AND labels not in (NewFeature,"Configuration","Forecasting/AccuracyImprovement","UI",DataTransfer,Enhancement)) OR (type = Extension AND labels not in ("VersionUpgrade",NewFeature,"Revision/Configuration","Implementation",Enhancement)) OR (type = Analysis AND labels not in ("KPIFollowups",InsightAnalysis,"PairControl","SpecialDayEffect","Seasonality","Extension","Cost",DiagnosticAnalysis,Simulation)) OR (type = Reporting AND labels not in ("Bug","New","Revision",UIBug,DataBug,LogicBug,ETL)) OR (type = Documentation AND labels not in ("Presentation/MeetingNotes","NewDocuments/Revision")) OR (type = Bug AND labels not in ("Bug","Dagfails",RunError,"Debug",UIBug,DataBug,LogicBug)) OR (type = "Fault (Off-Duty)" AND labels != "Fault(Off-Duty)") OR (type = "Version Upgrade" AND labels not in ("Meeting","Test","Bug","Documentation/Analysis")) OR (type = Handover AND labels not in ("Meeting","Documentation","QualityControl","LeftOver")) OR (type = "Int Call" AND labels not in (PlanningMeeting,"Meeting")) OR (type = "Client Call" AND labels not in (ClientMeetings,"ClientTrainingSessions")) OR (type = "Product Test" AND labels not in (QualityTest,MechanicTest)) OR (type = "R&D" AND labels not in (AgenticAI))) ORDER BY created DESC'


# ── Jira'dan task çekme fonksiyonu ───────────────────────────────────────────
def fetch_issues(jql, extra_fields=None):
    url = f"{JIRA_BASE_URL}/rest/api/3/search/jql"
    auth = (JIRA_EMAIL, JIRA_TOKEN)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    fields = ["summary", "assignee", "status", "labels"]
    if extra_fields:
        fields.extend(extra_fields)

    issues = []
    next_page_token = None

    while True:
        payload = {
            "jql": jql,
            "maxResults": 100,
            "fields": fields
        }
        if next_page_token:
            payload["nextPageToken"] = next_page_token

        resp = requests.post(url, auth=auth, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("issues", [])
        issues.extend(batch)

        if data.get("isLast", True):
            break
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    return issues


# ── Mention helper ────────────────────────────────────────────────────────────
def get_mention(assignee):
    if not assignee:
        return "_(atanmamış)_"
    email    = assignee.get("emailAddress", "")
    slack_id = EMAIL_TO_SLACK.get(email)
    return f"<@{slack_id}>" if slack_id else assignee.get("displayName", "?")


# ── Slack'e mesaj gönder ──────────────────────────────────────────────────────
def send_slack(text):
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_TOKEN}"},
        json={"channel": SLACK_CHANNEL, "text": text, "mrkdwn": True}
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"Slack hatası: {result.get('error')}")


# ── Ana akış ─────────────────────────────────────────────────────────────────
def main():

    # ── QUERY 1: Label'sız tasklar ────────────────────────────────────────────
    print("📋 Query 1: Label'sız tasklar çekiliyor...")
    issues_q1 = fetch_issues(JQL_NO_LABEL)
    print(f"   {len(issues_q1)} task bulundu.")

    lines_q1 = []
    for issue in issues_q1:
        key     = issue["key"]
        fields  = issue["fields"]
        status  = fields["status"]["statusCategory"]["key"]
        mention = get_mention(fields.get("assignee"))
        link    = f"<{JIRA_BASE_URL}/browse/{key}|{key}>"

        if status == "done":
            lines_q1.append(f"{mention} {link} taskını kapatmışsın üstelik label'sız halde oh ne güzel hayat! ‼️")
        else:
            lines_q1.append(f"{mention} sana atanmış {link} taskının label'ını düzeltmeyi unutma 🏷️")

    if lines_q1:
        send_slack("*🏷️ Label eksik tasklar:*\n" + "\n".join(lines_q1))
        print(f"   ✅ {len(lines_q1)} mesaj gönderildi.")
    else:
        print("   ℹ️ Gönderilecek task yok.")

    # ── QUERY 2: Related Project alanı boş ───────────────────────────────────
    print("📋 Query 2: Related Project boş tasklar çekiliyor...")
    issues_q2 = fetch_issues(JQL_NO_RELATED_PROJECT)
    print(f"   {len(issues_q2)} task bulundu.")

    lines_q2 = []
    for issue in issues_q2:
        key     = issue["key"]
        mention = get_mention(issue["fields"].get("assignee"))
        link    = f"<{JIRA_BASE_URL}/browse/{key}|{key}>"
        lines_q2.append(f"{mention} sana atanmış {link} taskının related project alanı boş 📂")

    if lines_q2:
        send_slack("*📂 Related Project alanı boş tasklar:*\n" + "\n".join(lines_q2))
        print(f"   ✅ {len(lines_q2)} mesaj gönderildi.")
    else:
        print("   ℹ️ Gönderilecek task yok.")

    # ── QUERY 3: Issue type ile uyumsuz label ─────────────────────────────────
    print("📋 Query 3: Uyumsuz label'lı tasklar çekiliyor...")
    issues_q3 = fetch_issues(JQL_WRONG_LABEL, extra_fields=["issuetype"])
    print(f"   {len(issues_q3)} task bulundu.")

    lines_q3 = []
    for issue in issues_q3:
        key     = issue["key"]
        mention = get_mention(issue["fields"].get("assignee"))
        link    = f"<{JIRA_BASE_URL}/browse/{key}|{key}>"
        lines_q3.append(f"{mention} sana atanmış {link} taskında issue type ile label'ın uyumlu olduğundan emin misin? 🤔")

    if lines_q3:
        send_slack("*🤔 Issue type / label uyumsuzluğu olan tasklar:*\n" + "\n".join(lines_q3))
        print(f"   ✅ {len(lines_q3)} mesaj gönderildi.")
    else:
        print("   ℹ️ Gönderilecek task yok.")


if __name__ == "__main__":
    main()
