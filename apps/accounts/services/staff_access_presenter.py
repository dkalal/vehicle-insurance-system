from apps.accounts.models import User


ROLE_ACCESS_GUIDE = [
    {
        'role': User.ROLE_ADMIN,
        'label': 'Admin',
        'summary': 'Leads tenant administration and can manage organization-wide operations.',
        'capabilities': [
            'Manage staff accounts',
            'Manage permit types',
            'Edit organization settings',
            'View reports and oversee operations',
            'Operate across all tenant vehicle scopes',
        ],
    },
    {
        'role': User.ROLE_MANAGER,
        'label': 'Manager',
        'summary': 'Oversees operations, reviews work, and supports controlled team administration.',
        'capabilities': [
            'View reports',
            'Review and verify payments',
            'Manage staff vehicle scope',
            'Oversee customer, vehicle, and policy work',
        ],
    },
    {
        'role': User.ROLE_AGENT,
        'label': 'Agent/Staff',
        'summary': 'Handles day-to-day operational work within assigned vehicle scope.',
        'capabilities': [
            'Create and update customers',
            'Create and update vehicles',
            'Create policies and record payments',
            'Operate within assigned vehicle scope',
        ],
    },
]


def get_role_access_guide():
    return ROLE_ACCESS_GUIDE


def get_effective_capabilities(*, user, has_vehicle_scope_limits):
    if getattr(user, 'role', None) == User.ROLE_ADMIN:
        capabilities = [
            'Can manage staff',
            'Can manage permit types',
            'Can edit organization settings',
            'Can view reports',
            'Can verify payments',
        ]
    elif getattr(user, 'role', None) == User.ROLE_MANAGER:
        capabilities = [
            'Can view reports',
            'Can verify payments',
            'Can manage vehicle scope',
            'Can oversee operations',
        ]
    else:
        capabilities = [
            'Can create customers',
            'Can manage vehicles',
            'Can create policies',
            'Can record payments',
        ]

    capabilities.append(
        'Can operate only within assigned vehicle types'
        if has_vehicle_scope_limits
        else 'Can operate across all vehicle types'
    )
    return capabilities
