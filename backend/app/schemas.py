from datetime import datetime, timezone
from typing import Literal, Any
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

Role = Literal["requester", "change_manager", "cab_member", "implementer", "admin"]
ChangeType = Literal["standard", "normal", "emergency"]
Risk = Literal["low", "moderate", "high", "very_high"]


def naive_utc(v):
    if isinstance(v, datetime) and v.tzinfo:
        return v.astimezone(timezone.utc).replace(tzinfo=None)
    return v


class In(BaseModel):
    @field_validator("*", mode="after")
    @classmethod
    def _utc(cls, v):
        return naive_utc(v)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserBrief(ORM):
    id: int
    full_name: str
    email: str
    role: str


class UserOut(UserBrief):
    is_active: bool
    is_approver: bool
    title: str | None = None
    organization_id: int


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: Role
    password: str
    is_approver: bool = False
    title: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    is_approver: bool | None = None
    title: str | None = None
    password: str | None = None


class GroupIn(BaseModel):
    name: str
    kind: Literal["assignment", "approval", "cab"] = "assignment"
    description: str | None = None
    member_ids: list[int] = []
    manager_id: int | None = None


class GroupOut(ORM, GroupIn):
    id: int


class GroupBrief(ORM):
    id: int
    name: str


class DelegationIn(In):
    delegate_id: int
    starts: datetime
    ends: datetime
    user_id: int | None = None


class DelegationOut(ORM):
    id: int
    starts: datetime
    ends: datetime
    approvals: bool
    user: UserBrief
    delegate: UserBrief


class CIIn(BaseModel):
    name: str
    ci_type: str = "server"
    owner: str | None = None
    environment: str = "production"
    criticality: Literal["low", "medium", "high", "critical"] = "medium"
    support_group_id: int | None = None
    description: str | None = None


class CIOut(ORM, CIIn):
    id: int


class RelIn(BaseModel):
    parent_id: int
    child_id: int
    rel_type: str = "depends_on"


class TemplateIn(BaseModel):
    name: str
    type: ChangeType = "standard"
    category: str | None = None
    description: str | None = None
    implementation_plan: str | None = None
    backout_plan: str | None = None
    test_plan: str | None = None
    pre_approved: bool = True
    risk: Risk = "low"
    active: bool = True


class TemplateOut(ORM, TemplateIn):
    id: int


class BlackoutIn(In):
    name: str
    start: datetime
    end: datetime
    reason: str | None = None


class BlackoutOut(ORM):
    id: int
    name: str
    start: datetime
    end: datetime
    reason: str | None


class MaintenanceIn(BaseModel):
    name: str
    weekdays: list[int]
    start_hour: int = 18
    end_hour: int = 23
    ci_id: int | None = None


class MaintenanceOut(ORM, MaintenanceIn):
    id: int


class PolicyIn(BaseModel):
    name: str
    stage: Literal["assess", "authorize"]
    change_type: Literal["*", "standard", "normal", "emergency"] = "*"
    min_risk: Risk = "low"
    max_risk: Risk = "very_high"
    group_id: int | None = None
    use_assignment_group: bool = False
    rule: Literal["any", "all"] = "any"
    auto_approve: bool = False
    active: bool = True
    order: int = 100


class PolicyOut(ORM, PolicyIn):
    id: int


class SLAIn(BaseModel):
    name: str
    change_type: str = "*"
    state: str
    target_hours: float


class SLAOut(ORM, SLAIn):
    id: int


class ChangeBase(In):
    title: str | None = None
    description: str | None = None
    justification: str | None = None
    type: ChangeType | None = None
    category: str | None = None
    configuration_item_id: int | None = None
    template_id: int | None = None
    assignment_group_id: int | None = None
    assigned_to_id: int | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    implementation_plan: str | None = None
    backout_plan: str | None = None
    test_plan: str | None = None
    close_code: Literal["successful", "successful_with_issues", "unsuccessful"] | None = None
    close_notes: str | None = None
    pir_notes: str | None = None
    on_hold: bool | None = None
    retrospective: bool | None = None
    verbal_auth_by: str | None = None
    no_ci: bool | None = None
    no_ci_reason: Literal['organization_wide', 'multiple_systems', 'process_policy', 'other'] | None = None
    no_ci_reason_other: str | None = None
    no_ci_scope: str | None = None
    verbal_auth_notes: str | None = None


class ChangeCreate(ChangeBase):
    title: str
    affected_ci_ids: list[int] = []


class ChangeOut(ORM):
    id: int
    number: str
    title: str
    description: str | None
    justification: str | None
    type: str
    category: str | None
    priority: str
    risk: str
    risk_score: int | None
    risk_answers: dict | None
    risk_conditions: list | None
    impact: str
    configuration_item_id: int | None
    configuration_item: CIOut | None
    template_id: int | None
    assignment_group_id: int | None
    assignment_group: GroupBrief | None
    planned_start: datetime | None
    planned_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    implementation_plan: str | None
    backout_plan: str | None
    test_plan: str | None
    requester_id: int
    requester: UserBrief | None
    assigned_to_id: int | None
    assigned_to: UserBrief | None
    state: str
    approval: str
    on_hold: bool
    close_code: str | None
    close_notes: str | None
    pir_notes: str | None
    source: str
    pipeline_ref: str | None
    retrospective: bool = False
    verbal_auth_by: str | None = None
    no_ci: bool = False
    no_ci_reason: str | None = None
    no_ci_reason_other: str | None = None
    no_ci_scope: str | None = None
    verbal_auth_notes: str | None = None
    retro_status: str | None = None
    retro_why_emergency: str | None = None
    retro_business_impact: str | None = None
    retro_actions_taken: str | None = None
    retro_timeline: str | None = None
    retro_outcome: str | None = None
    retro_root_cause: str | None = None
    retro_preventive_actions: str | None = None
    retro_submitted_at: datetime | None = None
    retro_info_request: str | None = None
    retro_decision_notes: str | None = None
    retro_decided_at: datetime | None = None
    retro_decided_by: UserBrief | None = None
    state_changed_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    allowed_transitions: list[str] = []
    retro_reviewer: bool = False
    retro_owner: bool = False
    path: list[str] = []
    sla: dict | None = None


class TransitionIn(BaseModel):
    to_state: str
    comment: str | None = None
    close_code: Literal["successful", "successful_with_issues", "unsuccessful"] | None = None
    close_notes: str | None = None
    pir_notes: str | None = None


class ApprovalAction(BaseModel):
    action: Literal["approve", "reject"]
    comments: str | None = None


class ApprovalOut(ORM):
    id: int
    change_id: int
    stage: str
    state: str
    rule: str
    comments: str | None
    created_at: datetime
    acted_at: datetime | None
    approver: UserBrief | None
    acted_by: UserBrief | None
    group: GroupBrief | None


class TaskIn(BaseModel):
    title: str
    task_type: Literal["planning", "implementation", "testing", "review"] = "implementation"
    description: str | None = None
    assigned_to_id: int | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assigned_to_id: int | None = None
    state: Literal["open", "in_progress", "closed", "canceled"] | None = None
    close_notes: str | None = None


class TaskOut(ORM):
    id: int
    change_id: int
    number: str
    task_type: str
    title: str
    description: str | None
    state: str
    close_notes: str | None
    assigned_to: UserBrief | None
    assigned_to_id: int | None
    created_at: datetime
    closed_at: datetime | None


class NoteIn(BaseModel):
    body: str
    kind: Literal["work", "comment"] = "work"


class NoteOut(ORM):
    id: int
    body: str
    kind: str
    created_at: datetime
    user: UserBrief


class EventOut(ORM):
    id: int
    event_type: str
    from_state: str | None
    to_state: str | None
    field: str | None
    old_value: str | None
    new_value: str | None
    comment: str | None
    created_at: datetime
    user: UserBrief | None


class RiskIn(BaseModel):
    answers: dict[str, Any]


class AIIn(BaseModel):
    change_id: int | None = None
    task: Literal["draft_plan", "summarize", "risk"]
    input: str | None = None


class MeetingIn(In):
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    chair_id: int | None = None
    attendee_ids: list[int] = []
    auto_agenda: bool = True


class MeetingUpdate(BaseModel):
    title: str | None = None
    location: str | None = None
    attendee_ids: list[int] | None = None
    status: Literal["scheduled", "in_progress", "completed", "canceled"] | None = None
    minutes: str | None = None


class AgendaOut(ORM):
    id: int
    change_id: int
    order: int
    decision: str
    notes: str | None
    change: ChangeOut


class MeetingOut(ORM):
    id: int
    title: str
    start: datetime
    end: datetime
    location: str | None
    chair: UserBrief | None
    attendee_ids: list
    status: str
    minutes: str | None


class RetroIn(BaseModel):
    retro_why_emergency: str | None = None
    retro_business_impact: str | None = None
    retro_actions_taken: str | None = None
    retro_timeline: str | None = None
    retro_outcome: str | None = None
    retro_root_cause: str | None = None
    retro_preventive_actions: str | None = None


class RetroDecisionIn(BaseModel):
    decision: Literal["request_info", "accepted", "accepted_with_actions", "rejected"]
    notes: str | None = None


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected", "deferred"]
    notes: str | None = None


class RecordIn(BaseModel):
    kind: Literal["incident", "problem"] = "incident"
    short_description: str
    priority: str = "3 - Moderate"
    state: str = "open"
    relation: Literal["fixes", "caused_by"] = "fixes"
    number: str | None = None


class RecordOut(ORM):
    id: int
    kind: str
    number: str
    short_description: str
    priority: str
    state: str
    change_id: int | None
    relation: str
    created_at: datetime


class WebhookIn(BaseModel):
    name: str | None = None
    url: str
    kind: Literal["generic", "slack", "teams"] = "generic"
    events: str = "*"
    secret: str | None = None
    is_active: bool = True


class WebhookOut(ORM, WebhookIn):
    id: int
    last_status: str | None


class TokenIn(BaseModel):
    name: str


class TokenOut(ORM):
    id: int
    name: str
    prefix: str
    last_used_at: datetime | None
    created_at: datetime
    token: str | None = None


class NotificationOut(ORM):
    id: int
    change_id: int | None
    message: str
    is_read: bool
    created_at: datetime


class DevOpsChangeIn(In):
    title: str
    pipeline_ref: str | None = None
    configuration_item_id: int | None = None
    ci_name: str | None = None
    template_id: int | None = None
    description: str | None = None
    planned_start: datetime | None = None
    duration_minutes: int = 60


class DevOpsCompleteIn(BaseModel):
    status: Literal["success", "failed"]
    notes: str | None = None
