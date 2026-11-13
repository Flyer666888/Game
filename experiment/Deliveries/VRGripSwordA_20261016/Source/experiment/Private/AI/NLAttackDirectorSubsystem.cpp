#include "AI/NLAttackDirectorSubsystem.h"

#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

namespace
{
bool IsLivingFighter(const AActor* Fighter, const UWorld* World)
{
	if (!IsValid(Fighter) || Fighter->GetWorld() != World)
	{
		return false;
	}
	const UNLCombatVitalsComponent* Vitals = Fighter->FindComponentByClass<UNLCombatVitalsComponent>();
	return !Vitals || !Vitals->IsDead();
}
}

void UNLAttackDirectorSubsystem::Tick(float DeltaTime)
{
	RemoveExpiredOrInvalidReservations();
	for (auto It = ActiveFighters.CreateIterator(); It; ++It)
	{
		if (!IsLivingFighter(It->Get(), GetWorld()))
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
	if (!GetWorld() || !IsLivingFighter(Fighter, GetWorld()))
	{
		RecordDiagnostic(TEXT("FighterInvalidOrDead"), Fighter);
		return false;
	}

	if (ActiveFighters.Contains(Fighter))
	{
		return true;
	}

	if (GetActiveFighterCount() >= FMath::Max(1, MaxActiveFighters))
	{
		RecordDiagnostic(TEXT("ActiveFighterLimit"), Fighter);
		return false;
	}

	ActiveFighters.Add(Fighter);
	RecordDiagnostic(TEXT("FighterRegistered"), Fighter);
	return true;
}

void UNLAttackDirectorSubsystem::UnregisterActiveFighter(AActor* Fighter)
{
	if (!Fighter)
	{
		return;
	}

	ActiveFighters.Remove(Fighter);
	for (auto It = Reservations.CreateIterator(); It; ++It)
	{
		if (It.Value().Owner.Get() == Fighter)
		{
			RecordCancellation(It.Key(), TEXT("OwnerUnregistered"), Fighter);
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
	FNLAttackSlotRequest Request;
	Request.Attacker = Attacker;
	Request.Slot = Slot;
	Request.ProjectedImpactTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	Request.ProjectedImpactTime += FMath::IsFinite(ProjectedImpactDelay)
		? FMath::Max(0.0f, ProjectedImpactDelay) : ProjectedImpactDelay;
	return AllocateAttackSlot(Request, false, OutReservationId);
}

bool UNLAttackDirectorSubsystem::RequestAttackSlot(
	const FNLAttackSlotRequest& Request, FGuid& OutReservationId)
{
	OutReservationId.Invalidate();
	UWorld* World = GetWorld();
	AActor* Attacker = Request.Attacker.Get();
	AActor* Target = Request.Target.Get();
	FName Rejection = NAME_None;
	if (!World || World->IsPaused())
	{
		Rejection = TEXT("CombatPaused");
	}
	else if (!IsLivingFighter(Attacker, World) || !ActiveFighters.Contains(Attacker))
	{
		Rejection = TEXT("AttackerNotActive");
	}
	else if (!IsLivingFighter(Target, World) || Target == Attacker)
	{
		Rejection = TEXT("TargetInvalidOrDead");
	}
	else
	{
		const UNLCombatIdentityComponent* EnemyIdentity = Attacker->FindComponentByClass<UNLCombatIdentityComponent>();
		const UNLCombatIdentityComponent* TargetIdentity = Target->FindComponentByClass<UNLCombatIdentityComponent>();
		const UNLCombatVitalsComponent* EnemyVitals = Attacker->FindComponentByClass<UNLCombatVitalsComponent>();
		const UNLCombatVitalsComponent* TargetVitals = Target->FindComponentByClass<UNLCombatVitalsComponent>();
		if (!EnemyIdentity || !TargetIdentity || !EnemyVitals || !TargetVitals ||
			!Request.EnemyRuntimeId.IsValid() || !Request.TargetRuntimeId.IsValid() ||
			EnemyIdentity->GetRuntimeId() != Request.EnemyRuntimeId ||
			TargetIdentity->GetRuntimeId() != Request.TargetRuntimeId)
		{
			Rejection = TEXT("CombatIdentityMismatch");
		}
		else if (EnemyIdentity->GetFaction() != ENLCombatFaction::Enemy ||
			(TargetIdentity->GetFaction() != ENLCombatFaction::Player &&
			 TargetIdentity->GetFaction() != ENLCombatFaction::Objective))
		{
			Rejection = TEXT("IllegalTargetFaction");
		}
		else if (!Request.AttackInstanceId.IsValid() || Request.AttackDefinitionId.IsNone())
		{
			Rejection = TEXT("MissingAttackIdentity");
		}
		else if (Request.AttackDirection.ContainsNaN() || Request.AttackDirection.IsNearlyZero() ||
			!FMath::IsFinite(Request.AttackDirection.SizeSquared()))
		{
			Rejection = TEXT("InvalidAttackDirection");
		}
		else if (!FMath::IsFinite(Request.TelegraphSeconds) || Request.TelegraphSeconds < 0.0f ||
			!FMath::IsFinite(Request.ProjectedImpactTime) ||
			Request.ProjectedImpactTime < World->GetTimeSeconds() + Request.TelegraphSeconds)
		{
			Rejection = TEXT("InvalidAttackTiming");
		}
		else if (!FMath::IsFinite(Request.ThreatWeight) || Request.ThreatWeight <= 0.0f)
		{
			Rejection = TEXT("InvalidThreatWeight");
		}
	}
	if (!Rejection.IsNone())
	{
		RecordRequestDiagnostic(Rejection, Request);
		return false;
	}
	return AllocateAttackSlot(Request, true, OutReservationId);
}

bool UNLAttackDirectorSubsystem::AllocateAttackSlot(
	const FNLAttackSlotRequest& Request, bool bStructuredRequest, FGuid& OutReservationId)
{
	OutReservationId.Invalidate();
	UWorld* World = GetWorld();
	AActor* Attacker = Request.Attacker.Get();
	const ENLAttackSlot Slot = Request.Slot;
	if (!World || World->IsPaused())
	{
		RecordRequestDiagnostic(TEXT("CombatPaused"), Request);
		return false;
	}
	if (!IsLivingFighter(Attacker, World) || !ActiveFighters.Contains(Attacker))
	{
		RecordRequestDiagnostic(TEXT("AttackerNotActive"), Request);
		return false;
	}
	if (!FMath::IsFinite(Request.ProjectedImpactTime) || GetSlotCapacity(Slot) <= 0)
	{
		RecordRequestDiagnostic(TEXT("InvalidAttackRequest"), Request);
		return false;
	}

	RemoveExpiredOrInvalidReservations();
	const double Now = World->GetTimeSeconds();
	const double Delay = Request.ProjectedImpactTime - Now;
	const double Timeout = FMath::Max(0.1f, ReservationTimeoutSeconds);
	if (Delay < 0.0 || Delay >= Timeout)
	{
		RecordRequestDiagnostic(TEXT("ImpactBeyondReservationTimeout"), Request);
		return false;
	}

	int32 SlotCount = 0;
	bool bHighThreatOccupied = false;
	const double ProjectedImpact = Request.ProjectedImpactTime;
	// The initial encounter always leaves at least 0.7 seconds between projected hits.
	const double RequiredSeparation = FMath::Max(0.7f, MinimumImpactSeparation);
	for (const TPair<FGuid, FNLAttackReservation>& Pair : Reservations)
	{
		const FNLAttackReservation& Existing = Pair.Value;
		if (Existing.Owner.Get() == Attacker)
		{
			RecordRequestDiagnostic(TEXT("OwnerAlreadyReserved"), Request, Pair.Key);
			return false;
		}
		if (bStructuredRequest && Existing.Request.AttackInstanceId == Request.AttackInstanceId)
		{
			RecordRequestDiagnostic(TEXT("AttackInstanceAlreadyReserved"), Request, Pair.Key);
			return false;
		}
		if (Existing.Slot == Slot)
		{
			++SlotCount;
		}
		bHighThreatOccupied |= Existing.Slot == ENLAttackSlot::HighThreat;
		if (FMath::Abs(Existing.ProjectedImpactTime - ProjectedImpact) < RequiredSeparation)
		{
			RecordRequestDiagnostic(TEXT("ImpactSeparation"), Request);
			return false;
		}
	}

	if ((Slot == ENLAttackSlot::HighThreat && Reservations.Num() > 0) ||
		(Slot != ENLAttackSlot::HighThreat && bHighThreatOccupied))
	{
		RecordRequestDiagnostic(TEXT("HighThreatExclusive"), Request);
		return false;
	}
	if (SlotCount >= GetSlotCapacity(Slot))
	{
		RecordRequestDiagnostic(TEXT("SlotCapacity"), Request);
		return false;
	}

	OutReservationId = FGuid::NewGuid();
	FNLAttackReservation& Reservation = Reservations.Add(OutReservationId);
	Reservation.Owner = Attacker;
	Reservation.Target = Request.Target.Get();
	Reservation.Request = Request;
	Reservation.Request.Attacker = nullptr;
	Reservation.Request.Target = nullptr;
	Reservation.Request.AttackDirection = Request.AttackDirection.GetSafeNormal();
	Reservation.bStructuredRequest = bStructuredRequest;
	Reservation.Slot = Slot;
	Reservation.ProjectedImpactTime = ProjectedImpact;
	Reservation.ExpiresAt = Now + Timeout;
	RecordRequestDiagnostic(TEXT("SlotGranted"), Request, OutReservationId, Reservation.ExpiresAt);
	return true;
}

void UNLAttackDirectorSubsystem::ReleaseAttackSlot(FGuid InReservationId)
{
	CancelAttackSlot(InReservationId, TEXT("Released"));
}

void UNLAttackDirectorSubsystem::CancelAttackSlot(FGuid InReservationId, FName Reason)
{
	if (const FNLAttackReservation* Existing = Reservations.Find(InReservationId))
	{
		AActor* Owner = Existing->Owner.Get();
		RecordCancellation(InReservationId, Reason.IsNone() ? FName(TEXT("Cancelled")) : Reason, Owner);
		Reservations.Remove(InReservationId);
	}
}

bool UNLAttackDirectorSubsystem::IsReservationValid(FGuid InReservationId, AActor* ExpectedOwner) const
{
	const FNLAttackReservation* Reservation = Reservations.Find(InReservationId);
	return InReservationId.IsValid() && Reservation &&
		(!ExpectedOwner || Reservation->Owner.Get() == ExpectedOwner) &&
		GetInvalidReservationReason(*Reservation).IsNone();
}

void UNLAttackDirectorSubsystem::ResetEncounter()
{
	for (const TPair<FGuid, FNLAttackReservation>& Pair : Reservations)
	{
		RecordCancellation(Pair.Key, TEXT("EncounterReset"), Pair.Value.Owner.Get());
	}
	Reservations.Reset();
	ActiveFighters.Reset();
	RecordDiagnostic(TEXT("EncounterReset"), nullptr);
}

FName UNLAttackDirectorSubsystem::GetReservationCancellationReason(FGuid InReservationId) const
{
	if (const FName* Reason = CancellationReasons.Find(InReservationId))
	{
		return *Reason;
	}
	const FNLAttackReservation* Reservation = Reservations.Find(InReservationId);
	if (Reservation)
	{
		return GetInvalidReservationReason(*Reservation);
	}
	return NAME_None;
}

bool UNLAttackDirectorSubsystem::GetReservationRequest(
	FGuid InReservationId, FNLAttackSlotRequest& OutRequest, double& OutExpiresAt) const
{
	OutRequest = FNLAttackSlotRequest();
	OutExpiresAt = 0.0;
	const FNLAttackReservation* Reservation = Reservations.Find(InReservationId);
	if (!Reservation)
	{
		return false;
	}
	OutRequest = Reservation->Request;
	OutRequest.Attacker = Reservation->Owner.Get();
	OutRequest.Target = Reservation->Target.Get();
	OutExpiresAt = Reservation->ExpiresAt;
	return true;
}

int32 UNLAttackDirectorSubsystem::GetActiveFighterCount() const
{
	int32 Count = 0;
	for (const TWeakObjectPtr<AActor>& Fighter : ActiveFighters)
	{
		Count += IsLivingFighter(Fighter.Get(), GetWorld()) ? 1 : 0;
	}
	return Count;
}

int32 UNLAttackDirectorSubsystem::GetReservationCount() const
{
	int32 Count = 0;
	for (const TPair<FGuid, FNLAttackReservation>& Pair : Reservations)
	{
		Count += IsReservationValid(Pair.Key) ? 1 : 0;
	}
	return Count;
}

void UNLAttackDirectorSubsystem::RemoveExpiredOrInvalidReservations()
{
	if (!GetWorld())
	{
		return;
	}

	for (auto It = Reservations.CreateIterator(); It; ++It)
	{
		const FNLAttackReservation& Reservation = It.Value();
		AActor* Owner = Reservation.Owner.Get();
		const FName Reason = GetInvalidReservationReason(Reservation);
		if (!Reason.IsNone())
		{
			RecordCancellation(It.Key(), Reason, Owner);
			It.RemoveCurrent();
		}
	}
}

FName UNLAttackDirectorSubsystem::GetInvalidReservationReason(const FNLAttackReservation& Reservation) const
{
	const UWorld* World = GetWorld();
	AActor* Owner = Reservation.Owner.Get();
	if (!World || !IsValid(Owner) || Owner->GetWorld() != World)
	{
		return TEXT("OwnerDestroyed");
	}
	if (!IsLivingFighter(Owner, World))
	{
		return TEXT("OwnerDead");
	}
	if (!ActiveFighters.Contains(Reservation.Owner))
	{
		return TEXT("OwnerUnregistered");
	}
	if (Reservation.bStructuredRequest)
	{
		AActor* Target = Reservation.Target.Get();
		if (!IsValid(Target) || Target->GetWorld() != World)
		{
			return TEXT("TargetDestroyed");
		}
		if (!IsLivingFighter(Target, World))
		{
			return TEXT("TargetDead");
		}
		const UNLCombatIdentityComponent* OwnerIdentity = Owner->FindComponentByClass<UNLCombatIdentityComponent>();
		const UNLCombatIdentityComponent* TargetIdentity = Target->FindComponentByClass<UNLCombatIdentityComponent>();
		if (!OwnerIdentity || !TargetIdentity ||
			OwnerIdentity->GetRuntimeId() != Reservation.Request.EnemyRuntimeId ||
			TargetIdentity->GetRuntimeId() != Reservation.Request.TargetRuntimeId)
		{
			return TEXT("CombatIdentityChanged");
		}
		if (OwnerIdentity->GetFaction() != ENLCombatFaction::Enemy ||
			(TargetIdentity->GetFaction() != ENLCombatFaction::Player &&
			 TargetIdentity->GetFaction() != ENLCombatFaction::Objective))
		{
			return TEXT("TargetFactionChanged");
		}
	}
	return World->GetTimeSeconds() >= Reservation.ExpiresAt
		? FName(TEXT("ReservationTimedOut")) : NAME_None;
}

void UNLAttackDirectorSubsystem::RecordDiagnostic(FName Reason, AActor* Owner, FGuid InReservationId)
{
	LastDiagnostic = FString::Printf(TEXT("%s | Actor=%s | Reservation=%s | GameTime=%.3f"),
		*Reason.ToString(), *GetNameSafe(Owner), *InReservationId.ToString(),
		GetWorld() ? static_cast<double>(GetWorld()->GetTimeSeconds()) : 0.0);
}

void UNLAttackDirectorSubsystem::RecordCancellation(FGuid InReservationId, FName Reason, AActor* Owner)
{
	if (!CancellationReasons.Contains(InReservationId))
	{
		CancellationOrder.Add(InReservationId);
	}
	CancellationReasons.Add(InReservationId, Reason);
	// Retain recent causes for brains that observe a timeout on their following tick.
	while (CancellationOrder.Num() > 128)
	{
		CancellationReasons.Remove(CancellationOrder[0]);
		CancellationOrder.RemoveAt(0);
	}
	if (const FNLAttackReservation* Reservation = Reservations.Find(InReservationId))
	{
		FNLAttackSlotRequest Request = Reservation->Request;
		Request.Attacker = Owner;
		Request.Target = Reservation->Target.Get();
		RecordRequestDiagnostic(Reason, Request, InReservationId, Reservation->ExpiresAt);
	}
	else
	{
		RecordDiagnostic(Reason, Owner, InReservationId);
	}
}

void UNLAttackDirectorSubsystem::RecordRequestDiagnostic(
	FName Reason, const FNLAttackSlotRequest& Request, FGuid InReservationId, double ExpiresAt)
{
	FNLAttackDirectorDiagnostic Diagnostic;
	Diagnostic.Reason = Reason;
	Diagnostic.ReservationId = InReservationId;
	Diagnostic.Request = Request;
	Diagnostic.Request.Attacker = nullptr;
	Diagnostic.Request.Target = nullptr;
	Diagnostic.AttackerName = GetNameSafe(Request.Attacker.Get());
	Diagnostic.TargetName = GetNameSafe(Request.Target.Get());
	Diagnostic.GameTime = GetWorld() ? static_cast<double>(GetWorld()->GetTimeSeconds()) : 0.0;
	Diagnostic.ExpiresAt = ExpiresAt;
	Diagnostic.bGranted = Reason == FName(TEXT("SlotGranted"));
	RecentDiagnostics.Add(Diagnostic);
	while (RecentDiagnostics.Num() > 128)
	{
		RecentDiagnostics.RemoveAt(0);
	}
	RecordDiagnostic(Reason, Request.Attacker.Get(), InReservationId);
	LastDiagnostic += FString::Printf(
		TEXT(" | Enemy=%s | Attack=%s/%s | Target=%s/%s | Direction=%s | Telegraph=%.3f | Impact=%.3f | Threat=%.3f | Slot=%d | Expires=%.3f"),
		*Request.EnemyRuntimeId.ToString(), *Request.AttackDefinitionId.ToString(),
		*Request.AttackInstanceId.ToString(), *Diagnostic.TargetName, *Request.TargetRuntimeId.ToString(),
		*Request.AttackDirection.ToCompactString(), Request.TelegraphSeconds, Request.ProjectedImpactTime,
		Request.ThreatWeight, static_cast<int32>(Request.Slot), ExpiresAt);
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
