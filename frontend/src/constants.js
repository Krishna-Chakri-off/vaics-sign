export const LABEL = { new: 'New', assess: 'Assess', authorize: 'Authorize', scheduled: 'Scheduled', implement: 'Implement', review: 'Review', closed: 'Closed', canceled: 'Canceled' }
export const STATES = Object.keys(LABEL)
export const STATE_STYLE = {
  new: 'bg-slate-50 text-slate-700 border-slate-300', assess: 'bg-amber-50 text-amber-800 border-amber-200',
  authorize: 'bg-orange-50 text-orange-700 border-orange-200', scheduled: 'bg-blue-50 text-blue-700 border-blue-200',
  implement: 'bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200', review: 'bg-yellow-50 text-yellow-800 border-yellow-200',
  closed: 'bg-green-50 text-green-700 border-green-200', canceled: 'bg-slate-100 text-slate-500 border-slate-300',
}
export const RISK_LABEL = { low: 'Low', moderate: 'Moderate', high: 'High', very_high: 'Very High' }
export const RISK_STYLE = { low: 'bg-green-50 text-green-700 border-green-200', moderate: 'bg-amber-50 text-amber-800 border-amber-200', high: 'bg-orange-50 text-orange-700 border-orange-200', very_high: 'bg-red-50 text-red-700 border-red-200' }
export const ROLE_LABEL = { requester: 'Requester', change_manager: 'Change Manager', cab_member: 'CAB Member', implementer: 'Implementer', admin: 'Administrator' }
export const RETRO_LABEL = { not_started: 'Not started', draft: 'Draft', submitted: 'Submitted to ECAB', info_requested: 'More info requested', accepted: 'Accepted', accepted_with_actions: 'Accepted with actions', rejected: 'Rejected - escalated' }
export const RETRO_FIELDS = [
  ['retro_why_emergency', 'Why was this an emergency?'], ['retro_business_impact', 'Business impact if it had not been done'],
  ['retro_actions_taken', 'What was done'], ['retro_timeline', 'Timeline of actions (times)'], ['retro_outcome', 'Outcome'],
  ['retro_root_cause', 'Root cause / related incident'], ['retro_preventive_actions', 'Preventive actions'],
]
export const CLOSE_CODES = { successful: 'Successful', successful_with_issues: 'Successful with issues', unsuccessful: 'Unsuccessful' }
export const ACTION = {
  assess: 'Request Approval', authorize: 'Request Authorization', scheduled: 'Schedule (pre-authorized)', implement: 'Implement',
  review: 'Review', closed: 'Close', new: 'Revert to New', canceled: 'Cancel Change',
}
