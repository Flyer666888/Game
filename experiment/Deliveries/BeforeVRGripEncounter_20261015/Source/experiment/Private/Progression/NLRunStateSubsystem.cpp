#include "Progression/NLRunStateSubsystem.h"

namespace
{
    constexpr int32 MaximumRewardEvents = 4096;
    bool IsValidProgression(const FNLProgressionState& State)
    {
        if (!FMath::IsFinite(State.LingQi) || State.LingQi < 0.0f || State.LingQi > 1000000.0f
            || !FMath::IsFinite(State.BurstEnergy) || State.BurstEnergy < 0.0f || State.BurstEnergy > 100.0f
            || State.UpgradeLevel < 1 || State.UpgradeLevel > 3 || State.RewardedEventIds.Num() > MaximumRewardEvents)
            return false;
        TSet<FName> Seen;
        for (FName EventId : State.RewardedEventIds)
        {
            if (EventId.IsNone() || EventId.ToString().Len() > 128 || Seen.Contains(EventId)) return false;
            Seen.Add(EventId);
        }
        return true;
    }
}

void UNLRunStateSubsystem::BeginRun(FGuid InRunId)
{
    if (!InRunId.IsValid())
    {
        LastFailureReason = TEXT("InvalidRunId");
        return;
    }
    if (RunId != InRunId)
    {
        RunId = InRunId;
        Progression = FNLProgressionState();
        OnRunStateChanged.Broadcast();
    }
    LastFailureReason = NAME_None;
}

bool UNLRunStateSubsystem::RestoreProgressionState(const FNLProgressionState& State)
{
    if (!RunId.IsValid() || !IsValidProgression(State))
    {
        LastFailureReason = TEXT("InvalidProgressionState");
        return false;
    }
    Progression = State;
    LastFailureReason = NAME_None;
    OnRunStateChanged.Broadcast();
    return true;
}

bool UNLRunStateSubsystem::RecordEnemyDefeat(FName StableEventId)
{
    if (!RunId.IsValid() || StableEventId.IsNone() || StableEventId.ToString().Len() > 128)
    {
        LastFailureReason = TEXT("InvalidRewardEvent");
        return false;
    }
    if (Progression.RewardedEventIds.Contains(StableEventId))
    {
        LastFailureReason = NAME_None;
        return false;
    }
    if (Progression.RewardedEventIds.Num() >= MaximumRewardEvents)
    {
        LastFailureReason = TEXT("RewardLedgerFull");
        return false;
    }
    Progression.RewardedEventIds.Add(StableEventId);
    LastFailureReason = NAME_None;
    OnRunStateChanged.Broadcast();
    return true;
}
