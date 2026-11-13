#include "Combat/NLCombatResolverSubsystem.h"

#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLGuardComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Misc/ScopeExit.h"

namespace
{
bool ValidateCombatContact(UWorld* World, AActor* SourceActor, AActor* TargetActor,
	const FNLCombatContact& Contact, UNLAttackDefinition* AttackDefinition, FName& FailureTag)
{
	if (!World || !IsValid(SourceActor) || !IsValid(TargetActor) || !IsValid(AttackDefinition)
		|| SourceActor->GetWorld() != World || TargetActor->GetWorld() != World)
	{
		FailureTag = TEXT("Combat.Ignored.InvalidContact");
		return false;
	}
	if (World->IsPaused())
	{
		FailureTag = TEXT("Combat.Ignored.Paused");
		return false;
	}

	UNLCombatIdentityComponent* SourceIdentity = SourceActor->FindComponentByClass<UNLCombatIdentityComponent>();
	UNLCombatIdentityComponent* TargetIdentity = TargetActor->FindComponentByClass<UNLCombatIdentityComponent>();
	if (!SourceIdentity || !TargetIdentity
		|| !Contact.AttackInstanceId.IsValid()
		|| !Contact.SourceRuntimeId.IsValid()
		|| !Contact.TargetRuntimeId.IsValid()
		|| SourceIdentity->EnsureRuntimeId() != Contact.SourceRuntimeId
		|| TargetIdentity->EnsureRuntimeId() != Contact.TargetRuntimeId
		|| AttackDefinition->StableId == NAME_None
		|| Contact.AttackDefinitionId != AttackDefinition->StableId)
	{
		FailureTag = TEXT("Combat.Ignored.InvalidIdentity");
		return false;
	}

	const ENLCombatFaction SourceFaction = SourceIdentity->GetFaction();
	const ENLCombatFaction TargetFaction = TargetIdentity->GetFaction();
	const bool bCanDamageTarget =
		(SourceFaction == ENLCombatFaction::Player &&
			(TargetFaction == ENLCombatFaction::Enemy || TargetFaction == ENLCombatFaction::Objective))
		|| (SourceFaction == ENLCombatFaction::Enemy &&
			(TargetFaction == ENLCombatFaction::Player || TargetFaction == ENLCombatFaction::Objective));
	if (!bCanDamageTarget)
	{
		FailureTag = TEXT("Combat.Ignored.FactionFilter");
		return false;
	}
	return true;
}
}

FNLCombatResult UNLCombatResolverSubsystem::ResolveContact(
	AActor* SourceActor,
	AActor* TargetActor,
	const FNLCombatContact& Contact,
	UNLAttackDefinition* AttackDefinition)
{
	FNLCombatResult Result;
	Result.AttackInstanceId = Contact.AttackInstanceId;
	Result.SourceRuntimeId = Contact.SourceRuntimeId;
	Result.TargetRuntimeId = Contact.TargetRuntimeId;

	if (!ValidateCombatContact(GetWorld(), SourceActor, TargetActor, Contact, AttackDefinition, Result.FeedbackTag))
	{
		return Publish(Result);
	}

	const FNLCombatHitKey HitKey{
		Contact.AttackInstanceId,
		Contact.TargetRuntimeId,
		Contact.ProjectileGeneration};
	if (ResolvedContacts.Contains(HitKey) || InFlightContacts.Contains(HitKey))
	{
		Result.FeedbackTag = TEXT("Combat.Ignored.DuplicateContact");
		return Publish(Result);
	}

	UNLCombatVitalsComponent* TargetVitals = TargetActor->FindComponentByClass<UNLCombatVitalsComponent>();
	if (!TargetVitals)
	{
		Result.FeedbackTag = TEXT("Combat.Ignored.MissingVitals");
		return Publish(Result);
	}
	if (TargetVitals->IsDead())
	{
		Result.FeedbackTag = TEXT("Combat.Ignored.DeadTarget");
		return Publish(Result);
	}
	if (TargetVitals->IsDamageProtected())
	{
		Result.FeedbackTag = TEXT("Combat.Ignored.DamageProtection");
		return Publish(Result);
	}

	InFlightContacts.Add(HitKey);
	ON_SCOPE_EXIT { InFlightContacts.Remove(HitKey); };
	const float AppliedDamage = TargetVitals->ApplyCombatDamage(AttackDefinition->Damage);

	if (AppliedDamage > 0.0f)
	{
		ResolvedContacts.Add(HitKey);
		Result.Outcome = ENLCombatOutcome::Hit;
		Result.AppliedDamage = AppliedDamage;
		Result.FeedbackTag = AttackDefinition->HitFeedbackTag;
	}
	else
	{
		Result.FeedbackTag = TEXT("Combat.Ignored.NoDamageApplied");
	}
	return Publish(Result);
}

FNLCombatResult UNLCombatResolverSubsystem::ResolveGuardContact(
	AActor* SourceActor,
	AActor* TargetActor,
	const FNLCombatContact& Contact,
	UNLAttackDefinition* AttackDefinition,
	UNLGuardComponent* GuardComponent,
	bool bAllowReflection)
{
	FNLCombatResult Result;
	Result.AttackInstanceId = Contact.AttackInstanceId;
	Result.SourceRuntimeId = Contact.SourceRuntimeId;
	Result.TargetRuntimeId = Contact.TargetRuntimeId;
	if (!ValidateCombatContact(GetWorld(), SourceActor, TargetActor, Contact, AttackDefinition, Result.FeedbackTag))
	{
		return Publish(Result);
	}
	const FNLCombatHitKey HitKey{Contact.AttackInstanceId, Contact.TargetRuntimeId, Contact.ProjectileGeneration};
	if (ResolvedContacts.Contains(HitKey) || InFlightContacts.Contains(HitKey))
	{
		Result.FeedbackTag = TEXT("Combat.Ignored.DuplicateContact");
		return Publish(Result);
	}
	if (!AttackDefinition->bCanBeBlocked)
	{
		Result.FeedbackTag = TEXT("Combat.Ignored.Unblockable");
		return Publish(Result);
	}
	if (!IsValid(GuardComponent) || GuardComponent->GetOwner() != TargetActor)
	{
		Result.FeedbackTag = TEXT("Combat.Ignored.InvalidGuard");
		return Publish(Result);
	}

	InFlightContacts.Add(HitKey);
	ON_SCOPE_EXIT { InFlightContacts.Remove(HitKey); };
	float GuardSpent = 0.0f;
	FNLCombatContact DefenseContact = Contact;
	if (Contact.ProjectileGeneration == INDEX_NONE)
	{
		// Lateral sword speed does not identify which side the attacker is on.
		DefenseContact.IncomingVelocity = Contact.HitPosition - SourceActor->GetActorLocation();
	}
	const bool bAllowPerfect = bAllowReflection && AttackDefinition->bCanBeParried
		&& AttackDefinition->bCanBeReflected && Contact.ProjectileGeneration >= 0;
	const ENLCombatOutcome GuardOutcome = GuardComponent->ResolveDefenseContact(DefenseContact, bAllowPerfect, GuardSpent);
	if (GuardOutcome == ENLCombatOutcome::Ignored)
	{
		Result.FeedbackTag = GuardComponent->IsGuardBroken()
			? TEXT("Combat.Ignored.GuardBroken") : TEXT("Combat.Ignored.GuardRejected");
		return Publish(Result);
	}

	ResolvedContacts.Add(HitKey);
	Result.Outcome = GuardOutcome;
	Result.GuardSpent = GuardSpent;
	if (GuardOutcome == ENLCombatOutcome::PerfectParry)
	{
		Result.NewProjectileFaction = TargetActor->FindComponentByClass<UNLCombatIdentityComponent>()->GetFaction();
		Result.FeedbackTag = TEXT("Combat.PerfectParry");
	}
	else
	{
		Result.FeedbackTag = TEXT("Combat.Blocked");
	}
	return Publish(Result);
}

void UNLCombatResolverSubsystem::ResetEncounterContacts()
{
	ResolvedContacts.Reset();
}

FNLCombatResult UNLCombatResolverSubsystem::Publish(FNLCombatResult Result)
{
	if (!Result.ResultId.IsValid())
	{
		Result.ResultId = FGuid::NewGuid();
	}
	OnCombatResult.Broadcast(Result);
	return Result;
}
