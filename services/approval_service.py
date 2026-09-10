from models.approval import ApprovalConfig


def effective_approval_stage(leave_request):
    """Resolve the active stage, including manager requests created before bypass."""
    level = leave_request.current_approval_level

    def config_at(stage):
        return ApprovalConfig.query.filter(
            ApprovalConfig.company_id == leave_request.company_id,
            (ApprovalConfig.leave_type_id == leave_request.leave_type_id)
            | ApprovalConfig.leave_type_id.is_(None),
            ApprovalConfig.level == stage,
        ).order_by(ApprovalConfig.leave_type_id.is_(None)).first()

    config = config_at(level)
    if leave_request.status == 'pending' and leave_request.employee.role == 'manager':
        while level < leave_request.max_approval_level and config and config.approver_role == 'manager':
            level += 1
            config = config_at(level)
    return level, config
