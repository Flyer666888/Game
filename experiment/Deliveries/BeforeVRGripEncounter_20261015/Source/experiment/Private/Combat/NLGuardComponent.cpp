#include "Combat/NLGuardComponent.h"

#include "Combat/NLCombatVitalsComponent.h"
#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

UNLGuardComponent::UNLGuardComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bTickEvenWhenPaused = false;
}

void UNLGuardComponent::BeginPlay()
{
	Super::BeginPlay();
	Vitals = GetOwner()->FindComponentByClass<UNLCombatVitalsComponent>();
	ConfigureGuard(GuardCollision, GuardVisual);
	ResetGuard();
}

void UNLGuardComponent::ConfigureGuard(UBoxComponent* Collision, USceneComponent* Visual)
{
	GuardCollision = Collision;
	GuardVisual = Visual;
	if (GuardCollision)
	{
		GuardCollision->ComponentTags.AddUnique(TEXT("NL_GuardCollision"));
		GuardCollision->SetCollisionObjectType(ECC_WorldDynamic);
		GuardCollision->SetCollisionResponseToAllChannels(ECR_Ignore);
		GuardCollision->SetCollisionResponseToChannel(ECC_GameTraceChannel3, ECR_Overlap);
		GuardCollision->SetCollisionResponseToChannel(ECC_GameTraceChannel2, ECR_Overlap);
		GuardCollision->SetGenerateOverlapEvents(false);
		GuardCollision->SetCanEverAffectNavigation(false);
	}
	SyncGuardPresentation();
}

UNLCombatVitalsComponent* UNLGuardComponent::GetVitals() const
{
	if (Vitals)
	{
		return Vitals;
	}
	return GetOwner() ? GetOwner()->FindComponentByClass<UNLCombatVitalsComponent>() : nullptr;
}

bool UNLGuardComponent::IsGuardBroken() const
{
	const UWorld* World = GetWorld();
	return bGuardBroken && World && World->GetTimeSeconds() < BreakEndsGameTime;
}

bool UNLGuardComponent::IsGuardActive() const
{
	const UWorld* World = GetWorld();
	const UNLCombatVitalsComponent* CurrentVitals = GetVitals();
	return World && !World->IsPaused() && GuardCollision && CurrentVitals && !CurrentVitals->IsDead()
		&& bGuardHeld && !bRequiresRelease && !IsGuardBroken() && CurrentVitals->GetGuard() > 0.0f;
}

float UNLGuardComponent::GetGuard() const
{
	const UNLCombatVitalsComponent* CurrentVitals = GetVitals();
	return CurrentVitals ? CurrentVitals->GetGuard() : 0.0f;
}

float UNLGuardComponent::GetMaxGuard() const
{
	const UNLCombatVitalsComponent* CurrentVitals = GetVitals();
	return CurrentVitals ? CurrentVitals->GetMaxGuard() : 0.0f;
}

float UNLGuardComponent::GetBreakRemainingSeconds() const
{
	const UWorld* World = GetWorld();
	return bGuardBroken && World ? static_cast<float>(FMath::Max(0.0, BreakEndsGameTime - World->GetTimeSeconds())) : 0.0f;
}

bool UNLGuardComponent::IsPerfectWindowActive() const
{
	const UWorld* World = GetWorld();
	return IsGuardActive() && bPerfectWindowAvailable && World
		&& World->GetTimeSeconds() < PerfectWindowEndsGameTime;
}

float UNLGuardComponent::GetPerfectWindowRemaining() const
{
	const UWorld* World = GetWorld();
	return IsPerfectWindowActive() && World
		? static_cast<float>(FMath::Max(0.0, PerfectWindowEndsGameTime - World->GetTimeSeconds())) : 0.0f;
}

void UNLGuardComponent::SetGuardHeld(bool bHeld)
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	if (!bHeld)
	{
		if (bGuardHeld || bRequiresRelease)
		{
			LastReleasedGameTime = World->GetTimeSeconds();
		}
		bGuardHeld = false;
		bRequiresRelease = false;
		bPerfectWindowAvailable = false;
		PerfectWindowEndsGameTime = 0.0;
	}
	else if (!World->IsPaused() && !bRequiresRelease && !IsGuardBroken())
	{
		UNLCombatVitalsComponent* CurrentVitals = GetVitals();
		if (CurrentVitals && !CurrentVitals->IsDead())
		{
			if (CurrentVitals->GetGuard() <= 0.0f)
			{
				BreakGuard();
			}
			else if (!bGuardHeld)
			{
				const double Now = World->GetTimeSeconds();
				const bool bReleasedLongEnough = bFirstPerfectRaiseAllowed
					|| Now >= LastReleasedGameTime + FMath::Max(0.0f, ReleaseRearmSeconds);
				const bool bRaisedFarEnoughApart = bFirstPerfectRaiseAllowed
					|| Now >= LastPerfectRaiseGameTime + FMath::Max(0.0f, MinimumPerfectRaiseInterval);
				bGuardHeld = true;
				bPerfectWindowAvailable = bReleasedLongEnough && bRaisedFarEnoughApart;
				if (bPerfectWindowAvailable)
				{
					PerfectWindowEndsGameTime = Now + FMath::Max(0.0f, PerfectWindowSeconds);
					LastPerfectRaiseGameTime = Now;
				}
				else
				{
					PerfectWindowEndsGameTime = 0.0;
				}
				bFirstPerfectRaiseAllowed = false;
			}
		}
	}
	SyncGuardPresentation();
}

void UNLGuardComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	UWorld* World = GetWorld();
	UNLCombatVitalsComponent* CurrentVitals = GetVitals();
	if (!World || World->IsPaused() || !CurrentVitals)
	{
		return;
	}
	const double Now = World->GetTimeSeconds();
	const double PreviousUpdate = LastUpdateGameTime;
	LastUpdateGameTime = Now;
	if (CurrentVitals->IsDead())
	{
		SetGuardHeld(false);
		return;
	}
	if (bGuardBroken && Now >= BreakEndsGameTime)
	{
		bGuardBroken = false;
	}
	if (IsGuardActive())
	{
		CurrentVitals->ConsumeGuard(FMath::Max(0.0f, MaintenanceCostPerSecond) * FMath::Max(0.0f, DeltaTime));
		if (CurrentVitals->GetGuard() <= 0.0f)
		{
			BreakGuard();
		}
	}
	else if (!bGuardHeld && !bRequiresRelease && !IsGuardBroken())
	{
		const double RecoveryStart = FMath::Max(PreviousUpdate,
			FMath::Max(LastReleasedGameTime + FMath::Max(0.0f, RecoveryDelaySeconds), BreakEndsGameTime));
		const float RecoveryTime = static_cast<float>(FMath::Max(0.0, Now - RecoveryStart));
		CurrentVitals->RestoreGuard(FMath::Max(0.0f, RecoveryPerSecond) * RecoveryTime);
	}
	SyncGuardPresentation();
}

bool UNLGuardComponent::TryBlockContact(const FNLCombatContact& Contact, float& OutGuardSpent)
{
	return ResolveDefenseContact(Contact, false, OutGuardSpent) == ENLCombatOutcome::Blocked;
}

ENLCombatOutcome UNLGuardComponent::ResolveDefenseContact(const FNLCombatContact& Contact,
	bool bAllowPerfect, float& OutGuardSpent)
{
	OutGuardSpent = 0.0f;
	if (!IsGuardActive() || Contact.HitPosition.ContainsNaN() || Contact.IncomingVelocity.ContainsNaN())
	{
		return ENLCombatOutcome::Ignored;
	}
	const FVector IncomingDirection = Contact.IncomingVelocity.GetSafeNormal();
	const FVector OutwardNormal = GuardCollision->GetForwardVector();
	if (IncomingDirection.IsNearlyZero()
		|| FVector::DotProduct(-IncomingDirection, OutwardNormal) < FMath::Clamp(MinimumFacingDot, 0.0f, 1.0f))
	{
		return ENLCombatOutcome::Ignored;
	}
	const FVector LocalContact = GuardCollision->GetComponentTransform().InverseTransformPosition(Contact.HitPosition);
	const FVector Extent = GuardCollision->GetUnscaledBoxExtent() + FVector(FMath::Max(0.0f, ContactPadding));
	if (FMath::Abs(LocalContact.X) > Extent.X || FMath::Abs(LocalContact.Y) > Extent.Y || FMath::Abs(LocalContact.Z) > Extent.Z)
	{
		return ENLCombatOutcome::Ignored;
	}

	UNLCombatVitalsComponent* CurrentVitals = GetVitals();
	const bool bPerfect = bAllowPerfect && IsPerfectWindowActive();
	const float OrdinaryCost = Contact.ProjectileGeneration == INDEX_NONE ? MeleeBlockGuardCost : BlockGuardCost;
	const float RequiredGuard = FMath::Max(0.0f, bPerfect ? PerfectGuardCost : OrdinaryCost);
	if (CurrentVitals->GetGuard() + KINDA_SMALL_NUMBER < RequiredGuard)
	{
		BreakGuard();
		return ENLCombatOutcome::Ignored;
	}
	OutGuardSpent = CurrentVitals->ConsumeGuard(RequiredGuard);
	if (bPerfect)
	{
		bPerfectWindowAvailable = false;
		PerfectWindowEndsGameTime = 0.0;
	}
	if (CurrentVitals->GetGuard() <= 0.0f)
	{
		BreakGuard();
	}
	return bPerfect ? ENLCombatOutcome::PerfectParry : ENLCombatOutcome::Blocked;
}

void UNLGuardComponent::BreakGuard()
{
	if (UNLCombatVitalsComponent* CurrentVitals = GetVitals())
	{
		CurrentVitals->ConsumeGuard(CurrentVitals->GetGuard());
	}
	bGuardHeld = false;
	bRequiresRelease = true;
	bGuardBroken = true;
	bPerfectWindowAvailable = false;
	PerfectWindowEndsGameTime = 0.0;
	if (const UWorld* World = GetWorld())
	{
		BreakEndsGameTime = World->GetTimeSeconds() + FMath::Max(0.0f, GuardBreakSeconds);
	}
	SyncGuardPresentation();
}

void UNLGuardComponent::ResetGuard()
{
	bGuardHeld = false;
	bGuardBroken = false;
	bRequiresRelease = false;
	bPerfectWindowAvailable = false;
	bFirstPerfectRaiseAllowed = true;
	BreakEndsGameTime = 0.0;
	PerfectWindowEndsGameTime = 0.0;
	LastPerfectRaiseGameTime = 0.0;
	const UWorld* World = GetWorld();
	LastReleasedGameTime = World ? World->GetTimeSeconds() : 0.0;
	LastUpdateGameTime = LastReleasedGameTime;
	SyncGuardPresentation();
}

void UNLGuardComponent::SyncGuardPresentation()
{
	const bool bActive = IsGuardActive();
	if (GuardCollision)
	{
		GuardCollision->SetCollisionEnabled(bActive ? ECollisionEnabled::QueryOnly : ECollisionEnabled::NoCollision);
	}
	if (GuardVisual)
	{
		GuardVisual->SetVisibility(bActive, true);
		GuardVisual->SetHiddenInGame(!bActive, true);
	}
	// Recursive visual updates include the attached collision box. Its wireframe
	// is authoring geometry; hiding its renderer does not disable query collision.
	if (GuardCollision)
	{
		GuardCollision->SetVisibility(false);
		GuardCollision->SetHiddenInGame(true);
	}
}
