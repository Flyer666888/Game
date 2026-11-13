#include "Progression/NLMasterRewardSubsystem.h"

#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Pickup/NLHealingPickup.h"
#include "Progression/NLRunStateSubsystem.h"

bool UNLMasterRewardSubsystem::DoesSupportWorldType(EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

UNLRunStateSubsystem* UNLMasterRewardSubsystem::ResolveRunState() const
{
    const UGameInstance* GameInstance = GetWorld() ? GetWorld()->GetGameInstance() : nullptr;
    return GameInstance ? GameInstance->GetSubsystem<UNLRunStateSubsystem>() : nullptr;
}

void UNLMasterRewardSubsystem::BindRunState()
{
    UNLRunStateSubsystem* State = ResolveRunState();
    if (BoundRunState == State) return;
    if (BoundRunState) BoundRunState->OnRunStateChanged.RemoveDynamic(this, &ThisClass::HandleRunStateChanged);
    BoundRunState = State;
    if (BoundRunState) BoundRunState->OnRunStateChanged.AddUniqueDynamic(this, &ThisClass::HandleRunStateChanged);
}

void UNLMasterRewardSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    BindRunState();
    RestorePendingRewards();
}

void UNLMasterRewardSubsystem::Deinitialize()
{
    if (BoundRunState) BoundRunState->OnRunStateChanged.RemoveDynamic(this, &ThisClass::HandleRunStateChanged);
    BoundRunState = nullptr;
    PendingRewards.Reset();
    Super::Deinitialize();
}

ANLHealingPickup* UNLMasterRewardSubsystem::GetPendingReward(FName MasterId) const
{
    const TWeakObjectPtr<ANLHealingPickup>* Existing = PendingRewards.Find(MasterId);
    ANLHealingPickup* Pickup = Existing ? Existing->Get() : nullptr;
    return IsValid(Pickup) && !Pickup->IsActorBeingDestroyed() ? Pickup : nullptr;
}

ANLHealingPickup* UNLMasterRewardSubsystem::CreatePendingReward(FName MasterId, FVector Location, AActor* Source)
{
    if (ANLHealingPickup* Existing = GetPendingReward(MasterId)) return Existing;
    if (!GetWorld() || !BoundRunState || BoundRunState->HasCollectedMasterReward(MasterId)
        || !FMath::IsFinite(RewardHealthAmount) || RewardHealthAmount <= 0.0f) return nullptr;
    FActorSpawnParameters Parameters;
    Parameters.Owner = IsValid(Source) ? Source : nullptr;
    Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    // Deferred construction prevents overlap before the stable reward identity is installed.
    Parameters.bDeferConstruction = true;
    ANLHealingPickup* Pickup = GetWorld()->SpawnActor<ANLHealingPickup>(Location, FRotator::ZeroRotator, Parameters);
    if (!Pickup) return nullptr;
    if (!Pickup->InitializeReward(MasterId, BoundRunState->GetRunId(), RewardHealthAmount))
    {
        Pickup->Destroy();
        return nullptr;
    }
    PendingRewards.Add(MasterId, Pickup);
    Pickup->FinishSpawning(FTransform(FRotator::ZeroRotator, Location));
    return Pickup;
}

ANLHealingPickup* UNLMasterRewardSubsystem::SpawnFirstDefeatReward(FName MasterId, FVector Location, AActor* InstigatorOptional)
{
    BindRunState();
    if (!BoundRunState || !BoundRunState->GetRunId().IsValid() || !UNLRunStateSubsystem::IsMasterId(MasterId)
        || Location.ContainsNaN() || Location.GetAbsMax() > 1.0e9) return nullptr;
    if (CurrentRunId != BoundRunState->GetRunId()) RestorePendingRewards();
    if (BoundRunState->HasCollectedMasterReward(MasterId)) return nullptr;
    if (!BoundRunState->HasDefeatedMaster(MasterId)
        && !BoundRunState->RecordMasterDefeat(MasterId, Location)) return nullptr;
    const FNLProgressionState State = BoundRunState->GetProgressionState();
    const FVector* SavedLocation = State.MasterRewardLocations.Find(MasterId);
    return SavedLocation ? CreatePendingReward(MasterId, *SavedLocation, InstigatorOptional) : nullptr;
}

void UNLMasterRewardSubsystem::HandleRunStateChanged()
{
    RestorePendingRewards();
}

void UNLMasterRewardSubsystem::RestorePendingRewards()
{
    if (bRefreshing || !GetWorld()) return;
    TGuardValue<bool> Guard(bRefreshing, true);
    BindRunState();
    if (!BoundRunState) return;
    const FGuid NewRun = BoundRunState->GetRunId();
    const FNLProgressionState State = BoundRunState->GetProgressionState();
    for (auto It = PendingRewards.CreateIterator(); It; ++It)
    {
        ANLHealingPickup* Pickup = It.Value().Get();
        if (CurrentRunId != NewRun || State.CollectedMasterRewards.Contains(It.Key())
            || !State.DefeatedMasterIds.Contains(It.Key()) || !IsValid(Pickup) || Pickup->IsActorBeingDestroyed())
        {
            if (IsValid(Pickup) && !Pickup->IsActorBeingDestroyed()) Pickup->Destroy();
            It.RemoveCurrent();
        }
    }
    CurrentRunId = NewRun;
    if (!NewRun.IsValid()) return;
    for (FName Id : State.DefeatedMasterIds)
        if (!State.CollectedMasterRewards.Contains(Id))
            if (const FVector* Position = State.MasterRewardLocations.Find(Id)) CreatePendingReward(Id, *Position, nullptr);
}
