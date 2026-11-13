#include "Objective/NLRitualObjective.h"

#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "CoreGlobals.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/ConstructorHelpers.h"

namespace NLRitual
{
    constexpr float CompleteProgress = 100.0f;
    constexpr int32 MaximumSources = 1024;
    bool IsStableId(FName Id) { return !Id.IsNone() && Id.ToString().Len() <= 128; }
}

ANLRitualObjective::ANLRitualObjective()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bTickEvenWhenPaused = false;
    PrimaryActorTick.TickGroup = TG_PostUpdateWork;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
    SetRootComponent(SceneRoot);
    RitualBody = CreateDefaultSubobject<UBoxComponent>(TEXT("RitualBody"));
    RitualBody->SetupAttachment(SceneRoot);
    RitualBody->SetRelativeLocation(FVector(0.0, 0.0, 55.0));
    RitualBody->InitBoxExtent(FVector(110.0, 110.0, 55.0));
    RitualBody->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    RitualBody->SetCollisionObjectType(ECC_WorldDynamic);
    RitualBody->SetCollisionResponseToAllChannels(ECR_Ignore);
    RitualBody->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
    RitualBody->SetCollisionResponseToChannel(ECC_GameTraceChannel2, ECR_Overlap);
    RitualBody->SetCollisionResponseToChannel(ECC_GameTraceChannel3, ECR_Block);
    RitualBody->SetCanEverAffectNavigation(false);
    RitualBody->ComponentTags.Add(TEXT("NL_RitualBody"));
    RitualVisual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("RitualVisual"));
    RitualVisual->SetupAttachment(SceneRoot);
    RitualVisual->SetRelativeLocation(FVector(0.0, 0.0, 4.0));
    RitualVisual->SetRelativeScale3D(FVector(2.4, 2.4, .08));
    RitualVisual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    RitualVisual->SetCanEverAffectNavigation(false);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    if (Cylinder.Succeeded()) RitualVisual->SetStaticMesh(Cylinder.Object);
    StatusText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("StatusText"));
    StatusText->SetupAttachment(SceneRoot);
    StatusText->SetRelativeLocation(FVector(0.0, 0.0, 165.0));
    StatusText->SetHorizontalAlignment(EHTA_Center);
    StatusText->SetWorldSize(12.0f);
    StatusText->SetTextRenderColor(FColor(90, 215, 225));
    StatusText->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    StatusText->SetCanEverAffectNavigation(false);
    CombatIdentity = CreateDefaultSubobject<UNLCombatIdentityComponent>(TEXT("CombatIdentity"));
    CombatIdentity->Faction = ENLCombatFaction::Objective;
    Vitals = CreateDefaultSubobject<UNLCombatVitalsComponent>(TEXT("Vitals"));
    Vitals->MaxHealth = 100.0f;
    Vitals->Health = 100.0f;
    Vitals->MaxGuard = 0.0f;
    Vitals->Guard = 0.0f;
    // The ritual has its own resource and no player's invulnerability timer.
    Vitals->DamageProtectionSeconds = 0.0f;
    Tags.Add(TEXT("NL_RitualObjective"));
}

void ANLRitualObjective::BeginPlay()
{
    Super::BeginPlay();
    Vitals->OnVitalsChanged.AddDynamic(this, &ANLRitualObjective::HandleVitalsChanged);
    ResetForEncounter(bStartActive);
}

void ANLRitualObjective::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    ClearAllSources();
    Vitals->OnVitalsChanged.RemoveDynamic(this, &ANLRitualObjective::HandleVitalsChanged);
    Super::EndPlay(EndPlayReason);
}

bool ANLRitualObjective::InitializeObjective(FName InStableId, float InMaxIntegrity, float InEffectiveRescueSeconds)
{
    if (!NLRitual::IsStableId(InStableId) || !FMath::IsFinite(InMaxIntegrity)
        || InMaxIntegrity < 1.0f || InMaxIntegrity > 1000000.0f || !FMath::IsFinite(InEffectiveRescueSeconds)
        || InEffectiveRescueSeconds < 1.0f || InEffectiveRescueSeconds > 86400.0f)
    {
        LastFailureReason = TEXT("Objective.InvalidConfiguration");
        return false;
    }
    ObjectiveStableId = InStableId;
    MaxIntegrity = InMaxIntegrity;
    EffectiveRescueSeconds = InEffectiveRescueSeconds;
    ResetForEncounter(bStartActive);
    return true;
}

void ANLRitualObjective::ResetForEncounter(bool bActivate)
{
    ++ResetGeneration;
    ClearAllSources();
    MaxIntegrity = FMath::IsFinite(MaxIntegrity) ? FMath::Clamp(MaxIntegrity, 1.0f, 1000000.0f) : 100.0f;
    EffectiveRescueSeconds = FMath::IsFinite(EffectiveRescueSeconds) ? FMath::Clamp(EffectiveRescueSeconds, 1.0f, 86400.0f) : 240.0f;
    bRestoringVitals = true;
    Vitals->MaxHealth = MaxIntegrity;
    Vitals->MaxGuard = 0.0f;
    Vitals->DamageProtectionSeconds = 0.0f;
    Vitals->RestoreResourcePreset(MaxIntegrity, 0.0f);
    bRestoringVitals = false;
    RescueProgress = 0.0f;
    LastObservedIntegrity = MaxIntegrity;
    LastRitualDamageGameTime = -1.0;
    bObjectiveActive = bActivate && NLRitual::IsStableId(ObjectiveStableId);
    bCombatPaused = false;
    bCompletionPending = bCompleted = bFailed = bAwaitingSourceRebuild = false;
    CompletionCandidateFrame = 0;
    LastFailureReason = bObjectiveActive || !bActivate ? NAME_None : FName(TEXT("Objective.InvalidStableId"));
    RitualBody->SetCollisionEnabled(bObjectiveActive ? ECollisionEnabled::QueryOnly : ECollisionEnabled::NoCollision);
    BroadcastChanged();
}

void ANLRitualObjective::SetObjectiveActive(bool bActive)
{
    if (bFailed || bCompleted) return;
    bObjectiveActive = bActive;
    RitualBody->SetCollisionEnabled(bActive ? ECollisionEnabled::QueryOnly : ECollisionEnabled::NoCollision);
    BroadcastChanged();
}

void ANLRitualObjective::SetCombatPaused(bool bPaused)
{
    bCombatPaused = bPaused;
    PruneInvalidSources();
    BroadcastChanged();
}

float ANLRitualObjective::GetIntegrity() const { return Vitals ? Vitals->GetHealth() : 0.0f; }

ENLRitualObjectiveState ANLRitualObjective::GetObjectiveState() const
{
    if (bFailed) return ENLRitualObjectiveState::Failed;
    if (bCompleted) return ENLRitualObjectiveState::Completed;
    if (!bObjectiveActive) return ENLRitualObjectiveState::Inactive;
    if (bCombatPaused || (GetWorld() && GetWorld()->IsPaused())) return ENLRitualObjectiveState::Paused;
    if (bAwaitingSourceRebuild) return ENLRitualObjectiveState::Restoring;
    if (bCompletionPending) return ENLRitualObjectiveState::CompletionPending;
    if (!InterferenceSources.IsEmpty()) return ENLRitualObjectiveState::Interfered;
    return ENLRitualObjectiveState::Running;
}

bool ANLRitualObjective::IsLiveEnemySource(AActor* Actor) const
{
    if (!IsValid(Actor) || Actor == this || Actor->GetWorld() != GetWorld()) return false;
    const UNLCombatIdentityComponent* Identity = Actor->FindComponentByClass<UNLCombatIdentityComponent>();
    const UNLCombatVitalsComponent* SourceVitals = Actor->FindComponentByClass<UNLCombatVitalsComponent>();
    return Identity && Identity->GetFaction() == ENLCombatFaction::Enemy && SourceVitals && !SourceVitals->IsDead();
}

bool ANLRitualObjective::IsLiveRequiredThreat(AActor* Actor) const
{
    if (!IsValid(Actor) || Actor->GetWorld() != GetWorld() || Actor->IsActorBeingDestroyed()) return false;
    if (const ANLCombatProjectile* Projectile = Cast<ANLCombatProjectile>(Actor))
    {
        // A fired shot remains a threat after its caster dies; reflection changes its faction.
        const AActor* Source = Projectile->GetSourceActor();
        const UNLCombatIdentityComponent* Identity = Source ? Source->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
        return Projectile->GetAttackInstanceId().IsValid() && Identity && Identity->GetFaction() == ENLCombatFaction::Enemy;
    }
    return IsLiveEnemySource(Actor);
}

void ANLRitualObjective::BindSource(AActor* Actor)
{
    Actor->OnDestroyed.AddUniqueDynamic(this, &ANLRitualObjective::HandleSourceDestroyed);
    if (UNLCombatVitalsComponent* SourceVitals = Actor->FindComponentByClass<UNLCombatVitalsComponent>())
        SourceVitals->OnDied.AddUniqueDynamic(this, &ANLRitualObjective::HandleSourceDied);
}

void ANLRitualObjective::UnbindUnusedSource(AActor* Actor)
{
    if (!IsValid(Actor)) return;
    for (const auto& Entry : InterferenceSources) if (Entry.Value.Get() == Actor) return;
    for (const auto& Entry : RemainingThreats) if (Entry.Value.Get() == Actor) return;
    Actor->OnDestroyed.RemoveDynamic(this, &ANLRitualObjective::HandleSourceDestroyed);
    if (UNLCombatVitalsComponent* SourceVitals = Actor->FindComponentByClass<UNLCombatVitalsComponent>())
        SourceVitals->OnDied.RemoveDynamic(this, &ANLRitualObjective::HandleSourceDied);
}

bool ANLRitualObjective::RegisterInterferenceSource(FName SourceId, AActor* SourceActor)
{
    if (!bObjectiveActive || bFailed || bCompleted || bCompletionPending || !NLRitual::IsStableId(SourceId)
        || !IsLiveEnemySource(SourceActor) || InterferenceSources.Contains(SourceId)
        || InterferenceSources.Num() >= NLRitual::MaximumSources)
        return false;
    for (const auto& Entry : InterferenceSources) if (Entry.Value.Get() == SourceActor) return false;
    InterferenceSources.Add(SourceId, SourceActor);
    ExpectedRestoredInterferenceIds.Remove(SourceId);
    BindSource(SourceActor);
    BroadcastChanged();
    return true;
}

bool ANLRitualObjective::UnregisterInterferenceSource(FName SourceId)
{
    const TWeakObjectPtr<AActor>* Existing = InterferenceSources.Find(SourceId);
    if (!Existing) return false;
    AActor* Actor = Existing->Get();
    InterferenceSources.Remove(SourceId);
    UnbindUnusedSource(Actor);
    BroadcastChanged();
    return true;
}

void ANLRitualObjective::ClearInterferenceSources()
{
    TArray<TWeakObjectPtr<AActor>> Actors;
    InterferenceSources.GenerateValueArray(Actors);
    InterferenceSources.Reset();
    ExpectedRestoredInterferenceIds.Reset();
    bAwaitingSourceRebuild = false;
    for (const TWeakObjectPtr<AActor>& Actor : Actors) UnbindUnusedSource(Actor.Get());
    BroadcastChanged();
}

bool ANLRitualObjective::RegisterRemainingThreat(FName SourceId, AActor* SourceActor)
{
    if (!bObjectiveActive || bFailed || bCompleted || !NLRitual::IsStableId(SourceId)
        || !IsLiveRequiredThreat(SourceActor) || RemainingThreats.Contains(SourceId)
        || RemainingThreats.Num() >= NLRitual::MaximumSources)
        return false;
    for (const auto& Entry : RemainingThreats) if (Entry.Value.Get() == SourceActor) return false;
    RemainingThreats.Add(SourceId, SourceActor);
    BindSource(SourceActor);
    BroadcastChanged();
    return true;
}

bool ANLRitualObjective::UnregisterRemainingThreat(FName SourceId)
{
    const TWeakObjectPtr<AActor>* Existing = RemainingThreats.Find(SourceId);
    if (!Existing) return false;
    AActor* Actor = Existing->Get();
    RemainingThreats.Remove(SourceId);
    UnbindUnusedSource(Actor);
    BroadcastChanged();
    return true;
}

void ANLRitualObjective::HandleSourceDied() { PruneInvalidSources(); }

void ANLRitualObjective::HandleSourceDestroyed(AActor* Actor)
{
    bool bChanged = false;
    for (auto It = InterferenceSources.CreateIterator(); It; ++It)
        if (It.Value().Get() == Actor || !It.Value().IsValid()) { It.RemoveCurrent(); bChanged = true; }
    for (auto It = RemainingThreats.CreateIterator(); It; ++It)
        if (It.Value().Get() == Actor || !It.Value().IsValid()) { It.RemoveCurrent(); bChanged = true; }
    UnbindUnusedSource(Actor);
    if (bChanged) BroadcastChanged();
}

void ANLRitualObjective::PruneInvalidSources()
{
    bool bChanged = false;
    TArray<TWeakObjectPtr<AActor>> Removed;
    for (auto It = InterferenceSources.CreateIterator(); It; ++It)
        if (!IsLiveEnemySource(It.Value().Get())) { Removed.Add(It.Value()); It.RemoveCurrent(); bChanged = true; }
    for (auto It = RemainingThreats.CreateIterator(); It; ++It)
        if (!IsLiveRequiredThreat(It.Value().Get())) { Removed.Add(It.Value()); It.RemoveCurrent(); bChanged = true; }
    for (const TWeakObjectPtr<AActor>& Actor : Removed) UnbindUnusedSource(Actor.Get());
    if (bChanged) BroadcastChanged();
}

void ANLRitualObjective::ClearAllSources()
{
    TArray<TWeakObjectPtr<AActor>> Actors;
    InterferenceSources.GenerateValueArray(Actors);
    TArray<TWeakObjectPtr<AActor>> ThreatActors;
    RemainingThreats.GenerateValueArray(ThreatActors);
    Actors.Append(ThreatActors);
    InterferenceSources.Reset();
    RemainingThreats.Reset();
    ExpectedRestoredInterferenceIds.Reset();
    for (const TWeakObjectPtr<AActor>& Actor : Actors) UnbindUnusedSource(Actor.Get());
}

FName ANLRitualObjective::GetAttackRejectionReason(AActor* SourceActor, UNLAttackDefinition* Definition) const
{
    if (!GetWorld() || !bObjectiveActive) return TEXT("Combat.Ignored.RitualInactive");
    if (bFailed || bCompleted) return TEXT("Combat.Ignored.RitualTerminal");
    if (bCombatPaused || GetWorld()->IsPaused() || bAwaitingSourceRebuild) return TEXT("Combat.Ignored.RitualPaused");
    if (!IsLiveEnemySource(SourceActor)) return TEXT("Combat.Ignored.RitualInvalidSource");
    if (!IsValid(Definition) || Definition->StableId.IsNone() || !AllowedAttackDefinitionIds.Contains(Definition->StableId))
        return TEXT("Combat.Ignored.RitualAttackNotAllowed");
    return NAME_None;
}

bool ANLRitualObjective::CanReceiveAttack(AActor* SourceActor, UNLAttackDefinition* Definition) const
{
    return GetAttackRejectionReason(SourceActor, Definition).IsNone();
}

void ANLRitualObjective::HandleVitalsChanged()
{
    if (bRestoringVitals) return;
    const float Integrity = GetIntegrity();
    if (Integrity < LastObservedIntegrity && GetWorld()) LastRitualDamageGameTime = GetWorld()->GetTimeSeconds();
    LastObservedIntegrity = Integrity;
    if (!bCompleted && !bFailed && Integrity <= 0.0f) { FailObjective(); return; }
    BroadcastChanged();
}

void ANLRitualObjective::FailObjective()
{
    if (bFailed || bCompleted) return;
    bFailed = true;
    bCompletionPending = false;
    bAwaitingSourceRebuild = false;
    ClearAllSources();
    RitualBody->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    const uint32 Generation = ResetGeneration;
    ++FailureEventCount;
    RefreshPresentation();
    OnObjectiveFailed.Broadcast(this);
    if (Generation == ResetGeneration) BroadcastChanged();
}

void ANLRitualObjective::CompleteObjective()
{
    if (bFailed || bCompleted || GetIntegrity() <= 0.0f) return;
    bCompleted = true;
    bCompletionPending = false;
    bAwaitingSourceRebuild = false;
    ClearAllSources();
    RitualBody->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    const uint32 Generation = ResetGeneration;
    ++CompletionEventCount;
    RefreshPresentation();
    OnRescueCompleted.Broadcast(this);
    if (Generation == ResetGeneration) BroadcastChanged();
}

void ANLRitualObjective::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    PruneInvalidSources();
    UWorld* World = GetWorld();
    if (!World) return;
    if (bFailed || bCompleted) { RefreshPresentation(); return; }
    if (GetIntegrity() <= 0.0f) { FailObjective(); return; }
    if (!bObjectiveActive || bCombatPaused || World->IsPaused() || bAwaitingSourceRebuild)
    { RefreshPresentation(); return; }
    if (bCompletionPending)
    {
        const uint32 Generation = ResetGeneration;
        OnBeforeCompletionCheck.Broadcast(this);
        if (Generation != ResetGeneration || bFailed || bCompleted || !bObjectiveActive || bCombatPaused) return;
        PruneInvalidSources();
        // A full-progress candidate cannot win until all damage from that frame has had
        // an opportunity to resolve. Integrity zero therefore deterministically wins ties.
        if (GFrameCounter > CompletionCandidateFrame && RemainingThreats.IsEmpty()) CompleteObjective();
        RefreshPresentation();
        return;
    }
    if (!InterferenceSources.IsEmpty() || !FMath::IsFinite(DeltaSeconds) || DeltaSeconds <= 0.0f)
    { RefreshPresentation(); return; }
    RescueProgress = FMath::Min(NLRitual::CompleteProgress,
        RescueProgress + DeltaSeconds * NLRitual::CompleteProgress / EffectiveRescueSeconds);
    if (RescueProgress >= NLRitual::CompleteProgress)
    {
        bCompletionPending = true;
        CompletionCandidateFrame = GFrameCounter;
        RefreshPresentation();
        OnCompletionPending.Broadcast(this);
    }
    BroadcastChanged();
}

FNLObjectiveSnapshot ANLRitualObjective::CaptureObjectiveSnapshot() const
{
    FNLObjectiveSnapshot Snapshot;
    Snapshot.StableId = ObjectiveStableId;
    Snapshot.Integrity = GetIntegrity();
    Snapshot.RescueProgress = RescueProgress;
    Snapshot.bCompleted = bCompleted;
    for (const auto& Entry : InterferenceSources)
        if (IsLiveEnemySource(Entry.Value.Get())) Snapshot.InterferenceSourceIds.Add(Entry.Key);
    for (FName Id : ExpectedRestoredInterferenceIds) Snapshot.InterferenceSourceIds.AddUnique(Id);
    Snapshot.InterferenceSourceIds.Sort(FNameLexicalLess());
    return Snapshot;
}

bool ANLRitualObjective::CanRestoreObjectiveSnapshot(const FNLObjectiveSnapshot& Snapshot, FName& OutReason) const
{
    OutReason = NAME_None;
    TSet<FName> UniqueIds;
    bool bValid = IsValid(Vitals) && IsValid(RitualBody) && NLRitual::IsStableId(Snapshot.StableId) && Snapshot.StableId == ObjectiveStableId
        && FMath::IsFinite(MaxIntegrity) && MaxIntegrity >= 1.0f && MaxIntegrity <= 1000000.0f
        && FMath::IsFinite(EffectiveRescueSeconds) && EffectiveRescueSeconds >= 1.0f && EffectiveRescueSeconds <= 86400.0f
        && FMath::IsFinite(Snapshot.Integrity) && Snapshot.Integrity >= 0.0f && Snapshot.Integrity <= MaxIntegrity
        && FMath::IsFinite(Snapshot.RescueProgress) && Snapshot.RescueProgress >= 0.0f
        && Snapshot.RescueProgress <= NLRitual::CompleteProgress
        && Snapshot.InterferenceSourceIds.Num() <= NLRitual::MaximumSources
        && (!Snapshot.bCompleted || (Snapshot.Integrity > 0.0f && Snapshot.RescueProgress == NLRitual::CompleteProgress))
        && (Snapshot.RescueProgress < NLRitual::CompleteProgress || Snapshot.InterferenceSourceIds.IsEmpty())
        && ((!Snapshot.bCompleted && Snapshot.Integrity > 0.0f) || Snapshot.InterferenceSourceIds.IsEmpty());
    for (FName Id : Snapshot.InterferenceSourceIds)
    {
        if (!NLRitual::IsStableId(Id) || UniqueIds.Contains(Id)) bValid = false;
        UniqueIds.Add(Id);
    }
    if (!bValid) OutReason = TEXT("Objective.InvalidSnapshot");
    return bValid;
}

bool ANLRitualObjective::RestoreObjectiveSnapshot(const FNLObjectiveSnapshot& Snapshot)
{
    if (!CanRestoreObjectiveSnapshot(Snapshot, LastFailureReason)) return false;
    TSet<FName> UniqueIds;
    for (FName Id : Snapshot.InterferenceSourceIds) UniqueIds.Add(Id);
    ++ResetGeneration;
    ClearAllSources();
    bRestoringVitals = true;
    Vitals->MaxHealth = MaxIntegrity;
    // RestoreResourcePreset deliberately rejects dead player presets. A dead ritual
    // snapshot is represented by zero integrity and a locked failure, without damage.
    Vitals->RestoreResourcePreset(FMath::Max(1.0f, Snapshot.Integrity), 0.0f);
    if (Snapshot.Integrity == 0.0f) Vitals->Health = 0.0f;
    bRestoringVitals = false;
    RescueProgress = Snapshot.RescueProgress;
    LastObservedIntegrity = Snapshot.Integrity;
    LastRitualDamageGameTime = -1.0;
    bCompleted = Snapshot.bCompleted;
    bFailed = Snapshot.Integrity <= 0.0f;
    bObjectiveActive = true;
    bCombatPaused = false;
    bCompletionPending = !bFailed && !bCompleted && RescueProgress >= NLRitual::CompleteProgress;
    CompletionCandidateFrame = GFrameCounter;
    ExpectedRestoredInterferenceIds = MoveTemp(UniqueIds);
    bAwaitingSourceRebuild = !ExpectedRestoredInterferenceIds.IsEmpty();
    RitualBody->SetCollisionEnabled(!bFailed && !bCompleted ? ECollisionEnabled::QueryOnly : ECollisionEnabled::NoCollision);
    LastFailureReason = NAME_None;
    // Loading a terminal snapshot restores its state; it never replays success/failure rewards.
    BroadcastChanged();
    return true;
}

int32 ANLRitualObjective::FinishSourceRebuild()
{
    PruneInvalidSources();
    const int32 Missing = ExpectedRestoredInterferenceIds.Num();
    ExpectedRestoredInterferenceIds.Reset();
    bAwaitingSourceRebuild = false;
    BroadcastChanged();
    return Missing;
}

void ANLRitualObjective::RefreshPresentation()
{
    if (!StatusText) return;
    const ENLRitualObjectiveState State = GetObjectiveState();
    const TCHAR* StateText = TEXT("PROTECT THE RITUAL");
    FColor Color(90, 215, 225);
    if (State == ENLRitualObjectiveState::Failed) { StateText = TEXT("RITUAL BROKEN"); Color = FColor(240, 80, 70); }
    else if (State == ENLRitualObjectiveState::Completed) { StateText = TEXT("RESCUE COMPLETE"); Color = FColor(100, 230, 140); }
    else if (State == ENLRitualObjectiveState::CompletionPending) { StateText = TEXT("CLEAR REMAINING THREATS"); Color = FColor(245, 210, 110); }
    else if (State == ENLRitualObjectiveState::Interfered) { StateText = TEXT("INTERRUPT THE CASTERS"); Color = FColor(245, 170, 70); }
    else if (State == ENLRitualObjectiveState::Paused) { StateText = TEXT("PAUSED"); }
    else if (State == ENLRitualObjectiveState::Restoring || State == ENLRitualObjectiveState::Inactive) { StateText = TEXT("RITUAL PREPARING"); }
    else if (GetWorld() && LastRitualDamageGameTime >= 0.0 && GetWorld()->GetTimeSeconds() - LastRitualDamageGameTime < 1.0)
    { StateText = TEXT("RITUAL DAMAGED"); Color = FColor(245, 140, 70); }
    StatusText->SetText(FText::FromString(FString::Printf(TEXT("%s\nINTEGRITY %.0f / %.0f\nRESCUE %.1f%%  |  INTERFERENCE %d"),
        StateText, GetIntegrity(), MaxIntegrity, RescueProgress, InterferenceSources.Num())));
    StatusText->SetTextRenderColor(Color);
    if (const APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
    {
        FVector Location; FRotator Rotation;
        PC->GetPlayerViewPoint(Location, Rotation);
        const FVector Direction = Location - StatusText->GetComponentLocation();
        if (!Direction.IsNearlyZero()) StatusText->SetWorldRotation(Direction.Rotation());
    }
}

void ANLRitualObjective::BroadcastChanged()
{
    RefreshPresentation();
    OnObjectiveChanged.Broadcast(this);
}
