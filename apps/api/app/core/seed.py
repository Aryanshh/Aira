import datetime
import uuid
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.security import hash_password, hash_pin, hash_token
from app.core.time import utc_now
from app.models.contact import Contact, ContactRole
from app.models.dose import DoseInstance, DoseStatus
from app.models.elder import CareLink, Elder, ElderCredentials
from app.models.medicine import Medicine, MedicineSchedule, Recurrence, StockEvent
from app.models.notification import NotificationPreference
from app.models.user import CareRole, Channel, NotifCategory, User
from app.services.medicine_service import MedicineService


async def seed_development_data(db: AsyncSession) -> None:
    """Idempotently seed standard development data for instant local testing."""
    # 1. Check if demo caregiver exists
    demo_email = "caregiver@aira.example.com"
    stmt = select(User).where(User.email == demo_email)
    existing_user = (await db.execute(stmt)).scalar_one_or_none()

    if not existing_user:
        logger.info("seeding_demo_caregiver", email=demo_email)
        user = User(
            id=uuid.uuid4(),
            email=demo_email,
            password_hash=hash_password("Password123!"),
            full_name="Anjali Sharma (Caregiver)",
            phone_e164="+919876543210",
            preferred_language="en",
            timezone="Asia/Kolkata",
            quiet_start=datetime.time(23, 0),
            quiet_end=datetime.time(6, 30),
            email_verified_at=utc_now(),
        )
        db.add(user)
        await db.flush()
        caregiver_user = user
    else:
        caregiver_user = existing_user

    # Also check if registered user exists (e.g. aryanshh08sri@gmail.com) and ensure verified
    registered_users = (await db.execute(select(User).where(User.email != demo_email))).scalars().all()
    for reg_user in registered_users:
        if not reg_user.email_verified_at:
            reg_user.email_verified_at = utc_now()

    # 2. Check if demo elder exists
    elder_stmt = select(Elder).where(Elder.full_name.like("%Ramesh Sharma%"))
    existing_elder = (await db.execute(elder_stmt)).scalar_one_or_none()

    if not existing_elder:
        logger.info("seeding_demo_elder", name="Ramesh Sharma (Dadaji)")
        elder_id = uuid.uuid4()
        demo_elder = Elder(
            id=elder_id,
            full_name="Ramesh Sharma",
            preferred_name="Dadaji",
            date_of_birth=datetime.date(1950, 4, 15),
            language="hi",
            timezone="Asia/Kolkata",
            day_close_time=datetime.time(23, 59),
            text_size=1,  # Large text
            created_by=caregiver_user.id,
        )
        db.add(demo_elder)
        await db.flush()

        # Credentials: AIRA-7K3Q, PIN 1234
        creds = ElderCredentials(
            elder_id=elder_id,
            access_code="AIRA-7K3Q",
            pin_hash=hash_pin("1234"),
            qr_token_hash=hash_token("demo-qr-token-aira-7k3q-secret-key-2026"),
        )
        db.add(creds)

        # Link caregiver as owner
        link = CareLink(
            id=uuid.uuid4(),
            elder_id=elder_id,
            user_id=caregiver_user.id,
            role=CareRole.CAREGIVER,
            is_owner=True,
            can_manage_medicines=True,
        )
        db.add(link)

        # Also link any registered users to this elder so they have an elder ready
        for reg_user in registered_users:
            link_stmt = select(CareLink).where(CareLink.elder_id == elder_id, CareLink.user_id == reg_user.id)
            if not (await db.execute(link_stmt)).scalar_one_or_none():
                db.add(CareLink(
                    id=uuid.uuid4(),
                    elder_id=elder_id,
                    user_id=reg_user.id,
                    role=CareRole.FAMILY,
                    is_owner=True,
                    can_manage_medicines=True,
                ))

        # 3. Emergency contacts
        contact1 = Contact(
            id=uuid.uuid4(),
            elder_id=elder_id,
            full_name="Dr. V. K. Sharma",
            role=ContactRole.DOCTOR,
            phone_e164="+919810012345",
            escalation_order=1,
        )
        contact2 = Contact(
            id=uuid.uuid4(),
            elder_id=elder_id,
            full_name="Priya Sharma",
            role=ContactRole.FAMILY,
            phone_e164="+919876543211",
            escalation_order=2,
        )
        db.add_all([contact1, contact2])

        # 4. Medicines
        tz = ZoneInfo("Asia/Kolkata")
        local_today = utc_now().astimezone(tz).date()

        # Med 1: Metformin 500mg (Daily: 08:00, 20:00)
        med1 = Medicine(
            id=uuid.uuid4(),
            elder_id=elder_id,
            name="Metformin",
            strength="500 mg",
            form="tablet",
            dose_amount=1.0,
            dose_unit="tablet",
            instructions="Take after breakfast and dinner",
            color_tag="blue",
            stock_quantity=58.0,
            refill_threshold_days=5,
            as_needed=False,
            created_by=caregiver_user.id,
        )
        db.add(med1)
        await db.flush()

        sched1 = MedicineSchedule(
            id=uuid.uuid4(),
            medicine_id=med1.id,
            start_date=local_today - datetime.timedelta(days=7),
            effective_from=local_today - datetime.timedelta(days=7),
            frequency=Recurrence.DAILY,
            times_of_day=["08:00", "20:00"],
        )
        db.add(sched1)

        db.add(StockEvent(
            id=uuid.uuid4(),
            medicine_id=med1.id,
            delta=60.0,
            reason="refill",
            note="Initial prescription pack",
        ))

        # Med 2: Amlodipine 5mg (Daily: 08:00)
        med2 = Medicine(
            id=uuid.uuid4(),
            elder_id=elder_id,
            name="Amlodipine",
            strength="5 mg",
            form="tablet",
            dose_amount=1.0,
            dose_unit="tablet",
            instructions="Every morning before breakfast",
            color_tag="amber",
            stock_quantity=28.0,
            refill_threshold_days=5,
            as_needed=False,
            created_by=caregiver_user.id,
        )
        db.add(med2)
        await db.flush()

        sched2 = MedicineSchedule(
            id=uuid.uuid4(),
            medicine_id=med2.id,
            start_date=local_today - datetime.timedelta(days=7),
            effective_from=local_today - datetime.timedelta(days=7),
            frequency=Recurrence.DAILY,
            times_of_day=["08:00"],
        )
        db.add(sched2)

        # Med 3: Paracetamol 650mg (As needed)
        med3 = Medicine(
            id=uuid.uuid4(),
            elder_id=elder_id,
            name="Paracetamol",
            strength="650 mg",
            form="tablet",
            dose_amount=1.0,
            dose_unit="tablet",
            instructions="Only if body temperature exceeds 100°F or severe body ache",
            color_tag="red",
            stock_quantity=20.0,
            refill_threshold_days=3,
            as_needed=True,
            created_by=caregiver_user.id,
        )
        db.add(med3)
        await db.flush()

        # 5. Generate rolling doses via MedicineService
        med_service = MedicineService(db)
        await med_service.generate_doses(med1, sched1, demo_elder, local_today, local_today + datetime.timedelta(days=7))
        await med_service.generate_doses(med2, sched2, demo_elder, local_today, local_today + datetime.timedelta(days=7))

        # Mark morning dose as taken
        morning_stmt = select(DoseInstance).where(
            DoseInstance.elder_id == elder_id,
            DoseInstance.scheduled_date == local_today,
            DoseInstance.scheduled_time == datetime.time(8, 0),
        )
        morning_doses = (await db.execute(morning_stmt)).scalars().all()
        for d in morning_doses:
            d.status = DoseStatus.TAKEN
            d.resolved_on = local_today
            d.resolved_by_actor = "elder"

        # 6. Default notification preferences for caregiver
        categories = [NotifCategory.SOS, NotifCategory.MISSED, NotifCategory.REFILL, NotifCategory.SYSTEM]
        channels = [Channel.IN_APP, Channel.EMAIL, Channel.SMS]
        for cat in categories:
            for ch in channels:
                enabled = True
                if ch == Channel.SMS and cat != NotifCategory.SOS:
                    enabled = False
                db.add(NotificationPreference(
                    user_id=caregiver_user.id,
                    category=cat,
                    channel=ch,
                    enabled=enabled,
                ))

        await db.commit()
        logger.info("demo_seed_completed_successfully")
    else:
        # If elder already exists, ensure all registered users are linked
        for reg_user in registered_users:
            link_stmt = select(CareLink).where(CareLink.elder_id == existing_elder.id, CareLink.user_id == reg_user.id)
            if not (await db.execute(link_stmt)).scalar_one_or_none():
                db.add(CareLink(
                    id=uuid.uuid4(),
                    elder_id=existing_elder.id,
                    user_id=reg_user.id,
                    role=CareRole.FAMILY,
                    is_owner=True,
                    can_manage_medicines=True,
                ))
        await db.commit()
