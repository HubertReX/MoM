---
tags:
  - dashboard
project_name: MoM
---

# 📊 MOAB Dashboard

> [!info] Dlaczego Dataview tu działa, a na tablicy nie
> **Dataview renderuje się tylko w zwykłych notatkach** (tryb Reading / Live Preview),
> a **nie** wewnątrz widoku Kanban (`board.md` przejmuje render). Dlatego zapytania
> trzymamy w tej notatce. Dataview czyta **frontmatter** notatek zadań z `Backlog/`
> (`status`, `priority`, `type`, `agent`, `owner`) — nie trzeba inline `pole:: wartość`,
> wystarczy frontmatter, który każde zadanie już ma.

## 🔢 Ile zadań w której kolumnie

```dataview
TABLE WITHOUT ID
  status AS "Lane",
  length(rows) AS "Ile"
FROM "Backlog"
WHERE status
GROUP BY status
SORT length(rows) DESC
```

## 🙋 Czeka na Ciebie (Needs You)

```dataview
TABLE WITHOUT ID
  link(file.link, id) AS "ID",
  title AS "Tytuł",
  priority AS "Prio",
  choice(agent, agent, "—") AS "Agent"
FROM "Backlog"
WHERE status = "needs-you"
SORT priority ASC
```

## 🟢 Kolejka dla AI (Ready for AI)

```dataview
TABLE WITHOUT ID
  link(file.link, id) AS "ID",
  title AS "Tytuł",
  priority AS "Prio",
  type AS "Typ"
FROM "Backlog"
WHERE status = "ready"
SORT priority ASC
```

## 🗂️ Wszystkie zadania

```dataview
TABLE WITHOUT ID
  link(file.link, id) AS "ID",
  title AS "Tytuł",
  status AS "Status",
  priority AS "Prio",
  type AS "Typ",
  choice(agent, agent, "—") AS "Agent",
  owner AS "Piłka"
FROM "Backlog"
WHERE id
SORT priority ASC, status ASC
```

## 🤖 W toku per agent

```dataview
TABLE WITHOUT ID
  choice(agent, agent, "—") AS "Agent",
  length(rows) AS "Aktywne"
FROM "Backlog"
WHERE status = "in-progress"
GROUP BY agent
```

---

> [!tip] WIP = 1/agent
> Jeśli w „W toku per agent" któryś agent ma > 1 — złamana zasada WIP. Każdy agent
> powinien mieć maks. jedną kartę w 🤖 In Progress.
