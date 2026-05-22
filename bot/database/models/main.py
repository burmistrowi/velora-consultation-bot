async def register_models() -> None:
    """Register all database models."""
    from .user import User
    from .slot import TimeSlot
    from .service import Service
    from .discount import Discount, DiscountService
    from .admin_user import AdminUser
    from .booking_meta import BookingMeta
    from .support_message import SupportMessage
    from .support_conversation import SupportConversation
    from .schedule_template import ScheduleTemplate
    from .template_rule import TemplateRule
    from .schedule_exception import ScheduleException