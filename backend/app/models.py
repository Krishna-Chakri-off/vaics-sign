from datetime import datetime, timezone
from sqlalchemy import false as sa_false, String, Integer, Text, DateTime, ForeignKey, Boolean, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def S(n=200, null=True, **kw):
    return mapped_column(String(n), nullable=null, **kw)


def T():
    return mapped_column(Text, nullable=True)


def DT(null=True, **kw):
    return mapped_column(DateTime, nullable=null, **kw)


def FK(t, null=True, **kw):
    return mapped_column(ForeignKey(t, ondelete=kw.pop("ondelete", None)), nullable=null, **kw)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = S(null=False)


class Group(Base):
    """Assignment / approval group (e.g. Network Team, CAB, ECAB, Technical Approvers)."""
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = S(null=False)
    kind: Mapped[str] = S(30, default="assignment")  # assignment|approval|cab
    description: Mapped[str | None] = T()
    member_ids: Mapped[list] = mapped_column(JSON, default=list)
    manager_id: Mapped[int | None] = FK("users.id")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, default=1, index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    full_name: Mapped[str] = S(null=False)
    role: Mapped[str] = S(30, null=False)
    is_approver: Mapped[bool] = mapped_column(Boolean, default=False)
    title: Mapped[str | None] = S()
    password_hash: Mapped[str] = S(null=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = DT(default=now)


class Delegation(Base):
    __tablename__ = "delegations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = FK("users.id", null=False)
    delegate_id: Mapped[int] = FK("users.id", null=False)
    starts: Mapped[datetime] = DT(null=False)
    ends: Mapped[datetime] = DT(null=False)
    approvals: Mapped[bool] = mapped_column(Boolean, default=True)
    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    delegate = relationship("User", foreign_keys=[delegate_id], lazy="joined")


class ConfigurationItem(Base):
    __tablename__ = "configuration_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, default=1, index=True)
    name: Mapped[str] = S(null=False)
    ci_type: Mapped[str] = S(50, default="server")  # business_service|application|database|server|network|cluster
    owner: Mapped[str | None] = S()
    environment: Mapped[str] = S(50, default="production")
    criticality: Mapped[str] = S(20, default="medium")  # low|medium|high|critical
    support_group_id: Mapped[int | None] = FK("groups.id")
    description: Mapped[str | None] = T()
    created_at: Mapped[datetime] = DT(default=now)


class CIRelationship(Base):
    """parent depends on child (e.g. 'Online Banking' service depends_on 'Web-Portal')."""
    __tablename__ = "ci_relationships"
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int] = FK("configuration_items.id", null=False, ondelete="CASCADE")
    child_id: Mapped[int] = FK("configuration_items.id", null=False, ondelete="CASCADE")
    rel_type: Mapped[str] = S(40, default="depends_on")


class ChangeTemplate(Base):
    """Standard change catalog item."""
    __tablename__ = "change_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, default=1, index=True)
    name: Mapped[str] = S(null=False)
    type: Mapped[str] = S(20, default="standard")
    category: Mapped[str | None] = S(100)
    description: Mapped[str | None] = T()
    implementation_plan: Mapped[str | None] = T()
    backout_plan: Mapped[str | None] = T()
    test_plan: Mapped[str | None] = T()
    pre_approved: Mapped[bool] = mapped_column(Boolean, default=True)
    risk: Mapped[str] = S(20, default="low")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = DT(default=now)


class BlackoutWindow(Base):
    __tablename__ = "blackout_windows"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, default=1, index=True)
    name: Mapped[str] = S(null=False)
    start: Mapped[datetime] = DT(null=False)
    end: Mapped[datetime] = DT(null=False)
    reason: Mapped[str | None] = T()


class MaintenanceWindow(Base):
    """Recurring weekly window. weekdays: 0=Mon..6=Sun. Hours in UTC. ci_id null = applies to all CIs."""
    __tablename__ = "maintenance_windows"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = S(null=False)
    weekdays: Mapped[list] = mapped_column(JSON, default=list)
    start_hour: Mapped[int] = mapped_column(Integer, default=18)
    end_hour: Mapped[int] = mapped_column(Integer, default=23)
    ci_id: Mapped[int | None] = FK("configuration_items.id")


class ApprovalPolicy(Base):
    """Which group approves at which stage, by change type and risk. auto_approve creates a system approval."""
    __tablename__ = "approval_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = S(null=False)
    stage: Mapped[str] = S(20, null=False)  # assess|authorize
    change_type: Mapped[str] = S(20, default="*")
    min_risk: Mapped[str] = S(20, default="low")
    max_risk: Mapped[str] = S(20, default="high")
    group_id: Mapped[int | None] = FK("groups.id")
    use_assignment_group: Mapped[bool] = mapped_column(Boolean, default=False)
    rule: Mapped[str] = S(10, default="any")  # any|all
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    order: Mapped[int] = mapped_column(Integer, default=100)
    group = relationship("Group", lazy="joined")


class SLADefinition(Base):
    __tablename__ = "sla_definitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = S(null=False)
    change_type: Mapped[str] = S(20, default="*")
    state: Mapped[str] = S(20, null=False)
    target_hours: Mapped[float] = mapped_column(Float, default=24)


class Change(Base):
    __tablename__ = "changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, default=1, index=True)
    number: Mapped[str] = mapped_column(String(20), unique=True, index=True, default="")
    title: Mapped[str] = S(300, null=False)
    description: Mapped[str | None] = T()
    justification: Mapped[str | None] = T()
    type: Mapped[str] = S(20, default="normal")
    category: Mapped[str | None] = S(100)
    priority: Mapped[str] = S(20, default="3 - Moderate")
    risk: Mapped[str] = S(20, default="moderate")  # low|moderate|high|very_high
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_conditions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    impact: Mapped[str] = S(20, default="2 - Medium")  # 1 - High|2 - Medium|3 - Low
    configuration_item_id: Mapped[int | None] = FK("configuration_items.id")
    template_id: Mapped[int | None] = FK("change_templates.id")
    assignment_group_id: Mapped[int | None] = FK("groups.id")
    planned_start: Mapped[datetime | None] = DT()
    planned_end: Mapped[datetime | None] = DT()
    actual_start: Mapped[datetime | None] = DT()
    actual_end: Mapped[datetime | None] = DT()
    implementation_plan: Mapped[str | None] = T()
    backout_plan: Mapped[str | None] = T()
    test_plan: Mapped[str | None] = T()
    requester_id: Mapped[int] = FK("users.id", null=False)
    assigned_to_id: Mapped[int | None] = FK("users.id")
    state: Mapped[str] = S(20, default="new", index=True)
    approval: Mapped[str] = S(20, default="not_requested")  # not_requested|requested|approved|rejected
    on_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    close_code: Mapped[str | None] = S(40)
    close_notes: Mapped[str | None] = T()
    pir_notes: Mapped[str | None] = T()
    source: Mapped[str] = S(30, default="portal")  # portal|devops|api
    pipeline_ref: Mapped[str | None] = S(300)
    # Retrospective emergency: implemented first, then mandatory ECAB/CAB retrospective review before closing
    retrospective: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    verbal_auth_by: Mapped[str | None] = S()
    # No specific CI (organization-wide / multi-system / process changes)
    no_ci: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    no_ci_reason: Mapped[str | None] = S(40)
    no_ci_reason_other: Mapped[str | None] = T()
    no_ci_scope: Mapped[str | None] = T()
    verbal_auth_notes: Mapped[str | None] = T()
    retro_status: Mapped[str | None] = S(30)  # not_started|draft|submitted|info_requested|accepted|accepted_with_actions|rejected
    retro_why_emergency: Mapped[str | None] = T()
    retro_business_impact: Mapped[str | None] = T()
    retro_actions_taken: Mapped[str | None] = T()
    retro_timeline: Mapped[str | None] = T()
    retro_outcome: Mapped[str | None] = T()
    retro_root_cause: Mapped[str | None] = T()
    retro_preventive_actions: Mapped[str | None] = T()
    retro_submitted_at: Mapped[datetime | None] = DT()
    retro_info_request: Mapped[str | None] = T()
    retro_decision_notes: Mapped[str | None] = T()
    retro_decided_at: Mapped[datetime | None] = DT()
    retro_decided_by_id: Mapped[int | None] = FK("users.id")
    state_changed_at: Mapped[datetime | None] = DT(default=now)
    closed_at: Mapped[datetime | None] = DT()
    created_at: Mapped[datetime] = DT(default=now)
    updated_at: Mapped[datetime] = DT(default=now, onupdate=now)

    requester = relationship("User", foreign_keys=[requester_id], lazy="joined")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id], lazy="joined")
    retro_decided_by = relationship("User", foreign_keys=[retro_decided_by_id], lazy="joined")
    configuration_item = relationship("ConfigurationItem", lazy="joined")
    assignment_group = relationship("Group", lazy="joined")


class ChangeCI(Base):
    """Affected CIs."""
    __tablename__ = "change_cis"
    id: Mapped[int] = mapped_column(primary_key=True)
    change_id: Mapped[int] = FK("changes.id", null=False, ondelete="CASCADE")
    ci_id: Mapped[int] = FK("configuration_items.id", null=False, ondelete="CASCADE")
    ci = relationship("ConfigurationItem", lazy="joined")


class ChangeTask(Base):
    __tablename__ = "change_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    change_id: Mapped[int] = FK("changes.id", null=False, ondelete="CASCADE")
    number: Mapped[str] = S(20, default="")
    task_type: Mapped[str] = S(20, default="implementation")  # planning|implementation|testing|review
    title: Mapped[str] = S(300, null=False)
    description: Mapped[str | None] = T()
    assigned_to_id: Mapped[int | None] = FK("users.id")
    state: Mapped[str] = S(20, default="open")  # open|in_progress|closed|canceled
    close_notes: Mapped[str | None] = T()
    order: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = DT(default=now)
    closed_at: Mapped[datetime | None] = DT()
    assigned_to = relationship("User", lazy="joined")


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    change_id: Mapped[int] = FK("changes.id", null=False, ondelete="CASCADE")
    stage: Mapped[str] = S(20, null=False)
    policy_id: Mapped[int | None] = FK("approval_policies.id")
    group_id: Mapped[int | None] = FK("groups.id")
    approver_id: Mapped[int | None] = FK("users.id")  # null = system auto-approval
    acted_by_id: Mapped[int | None] = FK("users.id")  # delegate who acted
    rule: Mapped[str] = S(10, default="any")
    state: Mapped[str] = S(20, default="requested")  # requested|approved|rejected|not_required|cancelled
    comments: Mapped[str | None] = T()
    created_at: Mapped[datetime] = DT(default=now)
    acted_at: Mapped[datetime | None] = DT()
    approver = relationship("User", foreign_keys=[approver_id], lazy="joined")
    acted_by = relationship("User", foreign_keys=[acted_by_id], lazy="joined")
    group = relationship("Group", lazy="joined")
    change = relationship("Change", lazy="joined")


class CabMeeting(Base):
    __tablename__ = "cab_meetings"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = S(null=False)
    start: Mapped[datetime] = DT(null=False)
    end: Mapped[datetime] = DT(null=False)
    location: Mapped[str | None] = S()
    chair_id: Mapped[int | None] = FK("users.id")
    attendee_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = S(20, default="scheduled")  # scheduled|in_progress|completed|canceled
    minutes: Mapped[str | None] = T()
    created_at: Mapped[datetime] = DT(default=now)
    chair = relationship("User", lazy="joined")


class CabAgendaItem(Base):
    __tablename__ = "cab_agenda_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = FK("cab_meetings.id", null=False, ondelete="CASCADE")
    change_id: Mapped[int] = FK("changes.id", null=False, ondelete="CASCADE")
    order: Mapped[int] = mapped_column(Integer, default=0)
    decision: Mapped[str] = S(20, default="pending")  # pending|approved|rejected|deferred
    notes: Mapped[str | None] = T()
    change = relationship("Change", lazy="joined")


class RelatedRecord(Base):
    """Incidents / problems related to a change."""
    __tablename__ = "related_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, default=1)
    kind: Mapped[str] = S(20, default="incident")  # incident|problem
    number: Mapped[str] = S(20, default="")
    short_description: Mapped[str] = S(300, null=False)
    priority: Mapped[str] = S(20, default="3 - Moderate")
    state: Mapped[str] = S(20, default="open")
    change_id: Mapped[int | None] = FK("changes.id", ondelete="SET NULL")
    relation: Mapped[str] = S(20, default="fixes")  # fixes (change resolves it) | caused_by (incident caused by change)
    created_at: Mapped[datetime] = DT(default=now)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    change_id: Mapped[int] = FK("changes.id", null=False, ondelete="CASCADE")
    user_id: Mapped[int | None] = FK("users.id")
    event_type: Mapped[str] = S(30, null=False)  # created|transition|field|note|approval|task|risk|cab|system
    from_state: Mapped[str | None] = S(20)
    to_state: Mapped[str | None] = S(20)
    field: Mapped[str | None] = S(60)
    old_value: Mapped[str | None] = T()
    new_value: Mapped[str | None] = T()
    comment: Mapped[str | None] = T()
    created_at: Mapped[datetime] = DT(default=now)
    user = relationship("User", lazy="joined")


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    change_id: Mapped[int] = FK("changes.id", null=False, ondelete="CASCADE")
    user_id: Mapped[int] = FK("users.id", null=False)
    kind: Mapped[str] = S(20, default="work")  # work|comment
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = DT(default=now)
    user = relationship("User", lazy="joined")


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = FK("users.id", null=False)
    change_id: Mapped[int | None] = FK("changes.id", ondelete="CASCADE")
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = DT(default=now)


class Webhook(Base):
    __tablename__ = "webhooks"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str | None] = S()
    url: Mapped[str] = S(500, null=False)
    kind: Mapped[str] = S(20, default="generic")  # generic|slack|teams
    events: Mapped[str] = S(200, default="*")
    secret: Mapped[str | None] = S()
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_status: Mapped[str | None] = S(100)
    created_at: Mapped[datetime] = DT(default=now)


class ApiToken(Base):
    __tablename__ = "api_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = FK("users.id", null=False)
    name: Mapped[str] = S(null=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    prefix: Mapped[str] = S(16, null=False)
    last_used_at: Mapped[datetime | None] = DT()
    created_at: Mapped[datetime] = DT(default=now)
