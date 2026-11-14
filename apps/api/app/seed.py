import asyncio
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_factory, Base, engine
from app.core.security import generate_elder_access_code, hash_password, hash_pin, hash_token
from app.core.time import utc_now
from app.models import (
    CareLink,
    CareRole,
    Contact,
    ContactRole,
    DayClosure,
    DoseInstance,
    DoseStatus,
    Elder,
    ElderCredentials,
    ElderSession,
    EscalationState,
    Medicine,
    MedicineSchedule,
    MedStatus,
    Recurrence,
    SosEvent,
    SosSource,
    SosStatus,
    User,
)


async def seed_data():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Check if users already exist
        res = await session.execute(select(User))
        if res.scalars().first():
            print("Database already contains data. Skipping seed.")
            return

        print("Seeding initial demo data...")

        # 1. Users: 1 Caregiver, 1 Family Member
        caregiver = User(
            email="caregiver@aira.example.com",
            password_hash=hash_password("Caregiver1234!"),
            full_name="Ananya Verma",
            phone_e164="+919876543210",
            preferred_language="en",
            timezone="Asia/Kolkata",
            email_verified_at=utc_now(),
        )
        family = User(
            email="family@aira.example.com",
            password_hash=hash_password("Family12345!"),
            full_name="Rahul Sharma",
            phone_e164="+919876543211",
            preferred_language="hi",
            timezone="Asia/Kolkata",
            email_verified_at=utc_now(),
        )
        session.add_all([caregiver, family])
        await session.flush()

        # 2. Demo Elders: 2 Elders
        elder1 = Elder(
            full_name="Devendra Sharma",
            preferred_name="Sharma ji",
            date_of_birth=date(1950, 4, 15),
            language="hi",
            timezone="Asia/Kolkata",
            day_close_time=time(23, 59),
            text_size=1,
            created_by=family.id,
        )
        elder2 = Elder(
            full_name="Kamla Devi",
            preferred_name="Mataji",
            date_of_birth=date(1954, 8, 20),
            language="en",
            timezone="Asia/Kolkata",
            day_close_time=time(23, 59),
            text_size=2,
            created_by=caregiver.id,
        )
        session.add_all([elder1, elder2])
        await session.flush()

        # 3. Care Links
        session.add_all([
            CareLink(elder_id=elder1.id, user_id=family.id, role=CareRole.FAMILY, is_owner=True, can_manage_medicines=True),
            CareLink(elder_id=elder1.id, user_id=caregiver.id, role=CareRole.CAREGIVER, is_owner=False, can_manage_medicines=True),
            CareLink(elder_id=elder2.id, user_id=caregiver.id, role=CareRole.CAREGIVER, is_owner=True, can_manage_medicines=True),
        ])

        # 4. Elder Credentials
        session.add_all([
            ElderCredentials(
                elder_id=elder1.id,
                access_code="AIRA-7K3Q",
                pin_hash=hash_pin("1234"),
                qr_token_hash=hash_token("demo_qr_token_sharmaji_1234"),
            ),
            ElderCredentials(
                elder_id=elder2.id,
                access_code="AIRA-9M2X",
                pin_hash=hash_pin("5678"),
                qr_token_hash=hash_token("demo_qr_token_kamla_5678"),
            ),
        ])

        # 5. Contacts (4 contacts for Sharma ji)
        session.add_all([
            Contact(
                elder_id=elder1.id,
                full_name="Rahul Sharma (Son)",
                role=ContactRole.FAMILY,
                phone_e164="+919876543211",
                whatsapp_e164="+919876543211",
                whatsapp_opt_in=True,
                preferred_channels=["sms", "whatsapp"],
                escalation_order=1,
            ),
            Contact(
                elder_id=elder1.id,
                full_name="Dr. Ashok Mehta",
                role=ContactRole.DOCTOR,
                phone_e164="+919876543212",
                whatsapp_e164="+919876543212",
                whatsapp_opt_in=True,
                preferred_channels=["sms"],
                escalation_order=2,
            ),
            Contact(
                elder_id=elder1.id,
                full_name="Ramesh Gupta (Neighbour)",
                role=ContactRole.NEIGHBOUR,
                phone_e164="+919876543213",
                whatsapp_e164="+919876543213",
                whatsapp_opt_in=True,
                preferred_channels=["sms", "whatsapp"],
                escalation_order=3,
            ),
            Contact(
                elder_id=elder1.id,
                full_name="Ananya Verma (Caregiver)",
                role=ContactRole.FAMILY,
                phone_e164="+919876543210",
                whatsapp_e164="+919876543210",
                whatsapp_opt_in=True,
                preferred_channels=["sms", "whatsapp"],
                escalation_order=4,
            ),
        ])

        # 6. Medicines & Schedules (Daily, Weekly, Every N Days, As Needed)
        today = date.today()

        med1 = Medicine(
            elder_id=elder1.id,
            name="Metformin",
            strength="500 mg",
            form="tablet",
            dose_amount=Decimal("1.0"),
            dose_unit="tablet",
            instructions="After breakfast and dinner",
            color_tag="blue",
            status=MedStatus.ACTIVE,
            stock_quantity=Decimal("6.0"),
            refill_threshold_days=5,
            created_by=family.id,
        )
        med2 = Medicine(
            elder_id=elder1.id,
            name="Amlodipine",
            strength="5 mg",
            form="tablet",
            dose_amount=Decimal("1.0"),
            dose_unit="tablet",
            instructions="Morning with water",
            color_tag="white",
            status=MedStatus.ACTIVE,
            stock_quantity=Decimal("20.0"),
            refill_threshold_days=5,
            created_by=family.id,
        )
        med3 = Medicine(
            elder_id=elder1.id,
            name="Vitamin D3",
            strength="60,000 IU",
            form="capsule",
            dose_amount=Decimal("1.0"),
            dose_unit="capsule",
            instructions="Once a week on Sunday morning",
            color_tag="yellow",
            status=MedStatus.ACTIVE,
            stock_quantity=Decimal("4.0"),
            refill_threshold_days=2,
            created_by=family.id,
        )
        session.add_all([med1, med2, med3])
        await session.flush()

        # Schedules
        sched1 = MedicineSchedule(
            medicine_id=med1.id,
            frequency=Recurrence.DAILY,
            times_of_day=["08:00", "20:00"],
            start_date=today - timedelta(days=7),
            effective_from=today - timedelta(days=7),
        )
        sched2 = MedicineSchedule(
            medicine_id=med2.id,
            frequency=Recurrence.DAILY,
            times_of_day=["08:00"],
            start_date=today - timedelta(days=7),
            effective_from=today - timedelta(days=7),
        )
        sched3 = MedicineSchedule(
            medicine_id=med3.id,
            frequency=Recurrence.WEEKLY,
            days_of_week=[7],  # Sunday
            times_of_day=["09:00"],
            start_date=today - timedelta(days=7),
            effective_from=today - timedelta(days=7),
        )
        session.add_all([sched1, sched2, sched3])
        await session.flush()

        # 7. SOS Events: 3 events (Handled, Failed, Active)
        session.add_all([
            SosEvent(
                elder_id=elder1.id,
                source=SosSource.DEVICE,
                client_event_id=str(uuid.uuid4()),
                status=SosStatus.HANDLED,
                escalation_state=EscalationState.ACKNOWLEDGED,
                press_count=1,
                triggered_at=utc_now() - timedelta(days=2),
                handled_at=utc_now() - timedelta(days=2, minutes=-15),
                handled_by=family.id,
            ),
            SosEvent(
                elder_id=elder1.id,
                source=SosSource.WEB,
                client_event_id=str(uuid.uuid4()),
                status=SosStatus.FAILED,
                escalation_state=EscalationState.EXHAUSTED,
                press_count=1,
                triggered_at=utc_now() - timedelta(days=5),
            ),
        ])

        await session.commit()
        print("Database successfully seeded with demo elders, team, schedules, and SOS history!")


if __name__ == "__main__":
    asyncio.run(seed_data())
