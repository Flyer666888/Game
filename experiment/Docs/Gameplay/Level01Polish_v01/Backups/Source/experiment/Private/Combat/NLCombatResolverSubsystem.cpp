#include "Combat/NLCombatResolverSubsystem.h"

#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLGuardComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "AI/NLEnemyBrainComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/Character.h"
#include "NavigationSystem.h"
#include "Objective/NLRitualObjective.h"
#include "EngineUtils.h"
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
		(SourceFaction == ENLCombatFaction::Player && TargetFaction == ENLCombatFaction::Enemy)
		|| (SourceFaction == ENLCombatFaction::Enemy &&
			(TargetFaction == ENLCombatFaction::Player || TargetFaction == ENLCombatFaction::Objective));
	if (!bCanDamageTarget)
	{
		FailureTag = TEXT("Combat.Ignored.FactionFilter");
		return false;
	}
	if (const ANLRitualObjective* Ritual = Cast<ANLRitualObjective>(TargetActor))
	{
		if (!Ritual->CanReceiveAttack(SourceActor, AttackDefinition))
		{
			FailureTag = Ritual->GetAttackRejectionReason(SourceActor, AttackDefinition);
			return false;
		}
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
		Result.TargetFaction = TargetActor->FindComponentByClass<UNLCombatIdentityComponent>()->GetFaction();
		Result.bTargetDefeated = TargetVitals->IsDead();
		Result.AppliedDamage = AppliedDamage;
		Result.FeedbackTag = AttackDefinition->HitFeedbackTag;
		if (Cast<ANLRitualObjective>(TargetActor))
		{
			Result.Outcome = ENLCombatOutcome::RitualDamaged;
			Result.FeedbackTag = TEXT("Combat.RitualDamaged");
		}
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
	// Melee parries use the same timed directional guard without requiring a
	// projectile reflection permission. Projectile perfect parries still reflect.
	const bool bIsMeleeContact = Contact.ProjectileGeneration == INDEX_NONE;
	const bool bAllowPerfect = AttackDefinition->bCanBeParried
		&& (bIsMeleeContact || (bAllowReflection && AttackDefinition->bCanBeReflected
			&& Contact.ProjectileGeneration >= 0));
	const ENLCombatOutcome GuardOutcome = GuardComponent->ResolveDefenseContact(DefenseContact, bAllowPerfect, GuardSpent);
	if (GuardOutcome == ENLCombatOutcome::Ignored)
	{
		Result.FeedbackTag = GuardComponent->IsGuardBroken()
			? TEXT("Combat.Ignored.GuardBroken") : TEXT("Combat.Ignored.GuardRejected");
		return Publish(Result);
	}

	ResolvedContacts.Add(HitKey);
	Result.Outcome = GuardOutcome;
	Result.TargetFaction = TargetActor->FindComponentByClass<UNLCombatIdentityComponent>()->GetFaction();
	Result.GuardSpent = GuardSpent;
	if (GuardOutcome == ENLCombatOutcome::PerfectParry)
	{
		if (!bIsMeleeContact)
		{
			Result.NewProjectileFaction = TargetActor->FindComponentByClass<UNLCombatIdentityComponent>()->GetFaction();
		}
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
	ResolvedAreaRequests.Reset();
}

FNLAreaControlResult UNLCombatResolverSubsystem::ResolveAreaControl(AActor* SourceActor, const FNLAreaControlRequest& Request)
{
	FNLAreaControlResult Result;
	Result.AbilityInstanceId = Request.AbilityInstanceId; Result.Ability = Request.Ability;
	UWorld* World = GetWorld();
	const UNLCombatIdentityComponent* SourceIdentity = IsValid(SourceActor) ? SourceActor->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
	const UNLCombatVitalsComponent* SourceVitals = IsValid(SourceActor) ? SourceActor->FindComponentByClass<UNLCombatVitalsComponent>() : nullptr;
	if (!World || !IsValid(SourceActor) || SourceActor->GetWorld() != World || World->IsPaused()
		|| !SourceIdentity || SourceIdentity->GetFaction() != ENLCombatFaction::Player || !SourceVitals || SourceVitals->IsDead()
		|| !Request.AbilityInstanceId.IsValid() || ResolvedAreaRequests.Contains(Request.AbilityInstanceId)
		|| (Request.Ability != ENLAreaAbility::Pulse && Request.Ability != ENLAreaAbility::Burst)
		|| !FMath::IsFinite(Request.RadiusCm) || Request.RadiusCm < 1.0f || Request.RadiusCm > 2000.0f
		|| !FMath::IsFinite(Request.StaggerSeconds) || Request.StaggerSeconds < 0.0f || Request.StaggerSeconds > 5.0f
		|| !FMath::IsFinite(Request.KnockbackCm) || Request.KnockbackCm < 0.0f || Request.KnockbackCm > 200.0f)
	{
		Result.FeedbackTag = TEXT("Ability.Ignored.InvalidOrRepeatedRequest"); return Result;
	}
	// Commit before cancellation/death delegates can re-enter the same instance.
	ResolvedAreaRequests.Add(Request.AbilityInstanceId);
	Result.bAccepted = true;
	Result.FeedbackTag = Request.Ability == ENLAreaAbility::Pulse ? TEXT("Ability.Pulse") : TEXT("Ability.Burst");
	const FVector Origin = SourceActor->GetActorLocation();
	const double RadiusSquared = FMath::Square(static_cast<double>(Request.RadiusCm));
	FCollisionQueryParams TraceParams(SCENE_QUERY_STAT(NilinAreaControlVisibility), false, SourceActor);
	// Combat bodies cannot shield one another from the wave; world geometry still blocks it.
	for (TActorIterator<AActor> It(World); It; ++It)
		if (It->FindComponentByClass<UNLCombatIdentityComponent>() || Cast<ANLCombatProjectile>(*It)) TraceParams.AddIgnoredActor(*It);
	auto HasLineOfSight = [&](const FVector& Point)
	{
		FHitResult Hit;
		return !World->LineTraceSingleByChannel(Hit, Origin, Point, ECC_Visibility, TraceParams);
	};
	for (TActorIterator<ANLCombatProjectile> It(World); It; ++It)
	{
		if (It->IsHostileToPlayer() && FVector::DistSquared(Origin, It->GetActorLocation()) <= RadiusSquared
			&& HasLineOfSight(It->GetActorLocation()))
		{
			if (It->Destroy()) ++Result.ProjectilesCleared;
		}
	}
	for (TActorIterator<ACharacter> It(World); It; ++It)
	{
		ACharacter* Enemy = *It;
		UNLCombatIdentityComponent* Identity = Enemy->FindComponentByClass<UNLCombatIdentityComponent>();
		UNLCombatVitalsComponent* Vitals = Enemy->FindComponentByClass<UNLCombatVitalsComponent>();
		UNLEnemyBrainComponent* Brain = Enemy->FindComponentByClass<UNLEnemyBrainComponent>();
		if (!Identity || Identity->GetFaction() != ENLCombatFaction::Enemy || !Vitals || Vitals->IsDead() || !Brain
			|| !FMath::IsFinite(Brain->AreaControlResponseScale) || Brain->AreaControlResponseScale <= 0.0f
			|| FVector::DistSquared(Origin, Enemy->GetActorLocation()) > RadiusSquared || !HasLineOfSight(Enemy->GetActorLocation())
			|| Brain->GetState() == ENLEnemyState::Paused || Brain->GetState() == ENLEnemyState::Despawn) continue;
		const float Response = FMath::Clamp(Brain->AreaControlResponseScale, 0.0f, 1.0f);
		Brain->ApplyStagger(Request.StaggerSeconds * Response);
		++Result.EnemiesInterrupted;
		// A knockback is a short swept displacement on the SAME connected NavMesh.
		// With missing navigation, an edge, excessive height change or a wall we keep the stagger only.
		UNavigationSystemV1* Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
		const FVector Start = Enemy->GetActorLocation();
		const FVector Direction = (Start - Origin).GetSafeNormal2D();
		const FVector Desired = Start + Direction * Request.KnockbackCm * Response;
		FNavLocation StartNav, EndNav;
		if (!Navigation || Direction.IsNearlyZero() || Request.KnockbackCm <= 0.0f
			|| !Navigation->ProjectPointToNavigation(Start, StartNav, FVector(4,4,200))
			|| !Navigation->ProjectPointToNavigation(Desired, EndNav, FVector(4,4,200))
			|| FVector::DistSquared2D(EndNav.Location, Desired) > FMath::Square(4.0f)
			|| FMath::Abs(EndNav.Location.Z - StartNav.Location.Z) > 20.0f) continue;
		FVector NavHit;
		if (UNavigationSystemV1::NavigationRaycast(World, StartNav.Location, EndNav.Location, NavHit, nullptr, Enemy->GetController())) continue;
		FVector Destination = EndNav.Location;
		Destination.Z += Start.Z - StartNav.Location.Z;
		FHitResult MoveHit;
		Enemy->SetActorLocation(Destination, true, &MoveHit, ETeleportType::None);
		if (FVector::DistSquared2D(Start, Enemy->GetActorLocation()) > 1.0f) ++Result.EnemiesMoved;
	}
	return Result;
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
