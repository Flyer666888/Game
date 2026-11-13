#include "AI/NLAttackDirectorSubsystem.h"

#include "GameFramework/Actor.h"

void UNLAttackDirectorSubsystem::Tick(float DeltaTime)
{
	RemoveExpiredOrInvalidReservations();
	for (auto It = ActiveFighters.CreateIterator(); It; ++It)
	{
		if (!It->IsValid())
		{
			It.RemoveCurrent();
		}
	}
}

TStatId UNLAttackDirectorSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UNLAttackDirectorSubsystem, STATGROUP_Tickables);
}

bool UNLAttackDirectorSubsystem::TryRegisterActiveFighter(AActor* Fighter)
{
	if (!IsValid(Fighter))
	{
		return false;
	}

	if (ActiveFighters.Contains(Fighter))
	{
		return true;
	}

	if (GetActiveFighterCount() >= MaxActiveFighters)
	{
		return false;
	}

	ActiveFighters.Add(Fighter);
	return true;
}

void UNLAttackDirectorSubsystem::UnregisterActiveFighter(AActor* Fighter)
{
	if (!IsValid(Fighter))
	{
		return;
	}

	ActiveFighters.Remove(Fighter);
	for (auto It = Reservations.CreateIterator(); It; ++It)
	{
		if (It.Value().Owner.Get() == Fighter)
		{
			It.RemoveCurrent();
		}
	}
}

bool UNLAttackDirectorSubsystem::TryAcquireAttackSlot(
	AActor* Attacker,
	ENLAttackSlot Slot,
	float ProjectedImpactDelay,
	FGuid& OutReservationId)
{
	OutReservationId.Invalidate();
	if (!IsValid(Attacker) || !ActiveFighters.Contains(Attacker) || !GetWorld())
	{
		return false;
	}

	RemoveExpiredOrInvalidReservations();
	int32 SlotCount = 0;
	bool bHighThreatOccupied = false;
	const double Now = GetWorld()->GetTimeSeconds();
	const double ProjectedImpact = Now + FMath::Max(0.0f, ProjectedImpactDelay);

	for (const TPair<FGuid, FNLAttackReservation>& Pair : Reservations)
	{
		const FNLAttackReservation& Existing = Pair.Value;
		if (Existing.Owner.Get() == Attacker)
		{
			return false;
		}
		if (Existing.Slot == Slot)
		{
			++SlotCount;
		}
		if (Existing.Slot == ENLAttackSlot::HighThreat)
		{
			bHighThreatOccupied = true;
		}
		if (FMath::Abs(Existing.ProjectedImpactTime - ProjectedImpact) < MinimumImpactSeparation)
		{
			return false;
		}
	}

	// High-threat attacks reserve an exclusive beat in the first prototype.
	if ((Slot == ENLAttackSlot::HighThreat && Reservations.Num() > 0) ||
		(Slot != ENLAttackSlot::HighThreat && bHighThreatOccupied) ||
		SlotCount >= GetSlotCapacity(Slot))
	{
		return false;
	}

	OutReservationId = FGuid::NewGuid();
	FNLAttackReservation& Reservation = Reservations.Add(OutReservationId);
	Reservation.Owner = Attacker;
	Reservation.Slot = Slot;
	Reservation.ProjectedImpactTime = ProjectedImpact;
	Reservation.ExpiresAt = Now + ReservationTimeoutSeconds;
	return true;
}

void UNLAttackDirectorSubsystem::ReleaseAttackSlot(FGuid ReservationId)
{
	if (ReservationId.IsValid())
	{
		Reservations.Remove(ReservationId);
	}
}

int32 UNLAttackDirectorSubsystem::GetActiveFighterCount() const
{
	int32 Count = 0;
	for (const TWeakObjectPtr<AActor>& Fighter : ActiveFighters)
	{
		Count += Fighter.IsValid() ? 1 : 0;
	}
	return Count;
}

void UNLAttackDirectorSubsystem::RemoveExpiredOrInvalidReservations()
{
	if (!GetWorld())
	{
		return;
	}

	const double Now = GetWorld()->GetTimeSeconds();
	for (auto It = Reservations.CreateIterator(); It; ++It)
	{
		if (!It.Value().Owner.IsValid() || Now >= It.Value().ExpiresAt)
		{
			It.RemoveCurrent();
		}
	}
}

int32 UNLAttackDirectorSubsystem::GetSlotCapacity(ENLAttackSlot Slot) const
{
	switch (Slot)
	{
	case ENLAttackSlot::Melee: return 2;
	case ENLAttackSlot::Ranged: return 1;
	case ENLAttackSlot::HighThreat: return 1;
	default: return 0;
	}
}
