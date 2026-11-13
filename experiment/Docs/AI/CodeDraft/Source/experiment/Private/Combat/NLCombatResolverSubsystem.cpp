#include "Combat/NLCombatResolverSubsystem.h"

#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"

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

	if (!SourceActor || !TargetActor || !AttackDefinition)
	{
		Result.FeedbackTag = TEXT("Combat.Ignored.InvalidContact");
		return Publish(Result);
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
		Result.FeedbackTag = TEXT("Combat.Ignored.InvalidIdentity");
		return Publish(Result);
	}

	const FNLCombatHitKey HitKey{
		Contact.AttackInstanceId,
		Contact.TargetRuntimeId,
		Contact.ProjectileGeneration};
	if (ResolvedContacts.Contains(HitKey))
	{
		Result.FeedbackTag = TEXT("Combat.Ignored.DuplicateContact");
		return Publish(Result);
	}
	ResolvedContacts.Add(HitKey);

	const ENLCombatFaction SourceFaction = SourceIdentity->GetFaction();
	const ENLCombatFaction TargetFaction = TargetIdentity->GetFaction();
	const bool bCanDamageTarget =
		(SourceFaction == ENLCombatFaction::Player &&
			(TargetFaction == ENLCombatFaction::Enemy || TargetFaction == ENLCombatFaction::Objective))
		|| (SourceFaction == ENLCombatFaction::Enemy &&
			(TargetFaction == ENLCombatFaction::Player || TargetFaction == ENLCombatFaction::Objective));
	if (!bCanDamageTarget)
	{
		Result.FeedbackTag = TEXT("Combat.Ignored.FactionFilter");
		return Publish(Result);
	}

	const float RequestedDamage = FMath::Max(0.0f, AttackDefinition->Damage);
	const APawn* SourcePawn = Cast<APawn>(SourceActor);
	const float AppliedDamage = UGameplayStatics::ApplyDamage(
		TargetActor,
		RequestedDamage,
		SourcePawn ? SourcePawn->GetController() : nullptr,
		SourceActor,
		nullptr);

	if (AppliedDamage > 0.0f)
	{
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
