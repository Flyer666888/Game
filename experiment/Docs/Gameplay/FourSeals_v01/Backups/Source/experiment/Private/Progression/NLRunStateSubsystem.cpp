#include "Progression/NLRunStateSubsystem.h"

#include "HAL/PlatformFileManager.h"
#include "Misc/Crc.h"
#include "Misc/Paths.h"
#include "Serialization/MemoryReader.h"
#include "Serialization/MemoryWriter.h"

#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#elif PLATFORM_LINUX || PLATFORM_MAC || PLATFORM_ANDROID || PLATFORM_IOS
#include <cstdio>
#endif

namespace
{
    constexpr int32 MaximumRewardEvents = 4096;
    constexpr uint32 MasterLedgerMagic = 0x4E4C4D52; // NLMR
    constexpr uint32 MasterLedgerVersion = 1;
    constexpr int32 MasterLedgerBytes = 4 + 4 + 16 + 1 + 1 + 4 * 3 * 8 + 4;

    FName MasterAt(int32 Index) { return FName(*FString::Printf(TEXT("GM%02d"), Index + 1)); }

    FString MasterLedgerPath(FGuid RunId)
    {
        return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(),
            TEXT("SaveGames/NilinMasterRewards"), RunId.ToString(EGuidFormats::Digits) + TEXT(".nlmr")));
    }

    bool AtomicReplaceLedger(const FString& Destination, const FString& Temp)
    {
#if PLATFORM_WINDOWS
        auto NativePath = [](FString Path)
        {
            Path = FPaths::ConvertRelativePathToFull(Path);
            FPaths::MakePlatformFilename(Path);
            if (!Path.StartsWith(TEXT("\\\\?\\")))
                Path = Path.StartsWith(TEXT("\\\\")) ? FString(TEXT("\\\\?\\UNC\\")) + Path.Mid(2)
                    : FString(TEXT("\\\\?\\")) + Path;
            return Path;
        };
        return !!::MoveFileExW(*NativePath(Temp), *NativePath(Destination),
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
#elif PLATFORM_LINUX || PLATFORM_MAC || PLATFORM_ANDROID || PLATFORM_IOS
        return ::rename(TCHAR_TO_UTF8(*Temp), TCHAR_TO_UTF8(*Destination)) == 0;
#else
        return false;
#endif
    }

    void MergeMasterLedgers(FNLProgressionState& Destination, const FNLProgressionState& Source)
    {
        for (FName Id : Source.DefeatedMasterIds)
        {
            Destination.DefeatedMasterIds.AddUnique(Id);
            // The first drop's position wins during rollback/repeated defeat events.
            if (const FVector* Position = Source.MasterRewardLocations.Find(Id))
                Destination.MasterRewardLocations.FindOrAdd(Id) = *Position;
        }
        for (FName Id : Source.CollectedMasterRewards) Destination.CollectedMasterRewards.AddUnique(Id);
    }
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
        return UNLRunStateSubsystem::ValidateMasterRewards(State);
    }
}

bool UNLRunStateSubsystem::IsMasterId(FName MasterId)
{
    return MasterId == TEXT("GM01") || MasterId == TEXT("GM02")
        || MasterId == TEXT("GM03") || MasterId == TEXT("GM04");
}

bool UNLRunStateSubsystem::ValidateMasterRewards(const FNLProgressionState& State)
{
    if (State.DefeatedMasterIds.Num() > 4 || State.CollectedMasterRewards.Num() > 4
        || State.MasterRewardLocations.Num() != State.DefeatedMasterIds.Num()) return false;
    TSet<FName> Seen;
    for (FName Id : State.DefeatedMasterIds)
    {
        const FVector* Position = State.MasterRewardLocations.Find(Id);
        if (!IsMasterId(Id) || Seen.Contains(Id) || !Position || Position->ContainsNaN()
            || Position->GetAbsMax() > 1.0e9) return false;
        Seen.Add(Id);
    }
    Seen.Reset();
    for (FName Id : State.CollectedMasterRewards)
    {
        if (!State.DefeatedMasterIds.Contains(Id) || Seen.Contains(Id)) return false;
        Seen.Add(Id);
    }
    return true;
}

bool UNLRunStateSubsystem::LoadMasterLedger(FNLProgressionState& State)
{
    IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
    const FString Path = MasterLedgerPath(RunId);
    if (!Files.FileExists(*Path)) return true;
    TUniquePtr<IFileHandle> Handle(Files.OpenRead(*Path));
    TArray<uint8> Bytes;
    Bytes.SetNumUninitialized(MasterLedgerBytes);
    if (!Handle || Handle->Size() != MasterLedgerBytes || !Handle->Read(Bytes.GetData(), Bytes.Num()))
        return false;
    uint32 ExpectedCrc = 0;
    FMemory::Memcpy(&ExpectedCrc, Bytes.GetData() + Bytes.Num() - sizeof(uint32), sizeof(uint32));
    if (ExpectedCrc != FCrc::MemCrc32(Bytes.GetData(), Bytes.Num() - sizeof(uint32))) return false;
    FMemoryReader Reader(Bytes, true);
    uint32 Magic = 0, Version = 0;
    FGuid StoredRun;
    uint8 DefeatedMask = 0, CollectedMask = 0;
    Reader << Magic << Version << StoredRun << DefeatedMask << CollectedMask;
    if (Magic != MasterLedgerMagic || Version != MasterLedgerVersion || StoredRun != RunId
        || DefeatedMask > 15 || CollectedMask > 15 || (CollectedMask & ~DefeatedMask) != 0) return false;
    FNLProgressionState Ledger;
    for (int32 Index = 0; Index < 4; ++Index)
    {
        double X = 0, Y = 0, Z = 0;
        Reader << X << Y << Z;
        const FVector Position(X, Y, Z);
        if (Position.ContainsNaN() || Position.GetAbsMax() > 1.0e9) return false;
        if ((DefeatedMask & (1 << Index)) != 0)
        {
            const FName Id = MasterAt(Index);
            Ledger.DefeatedMasterIds.Add(Id);
            Ledger.MasterRewardLocations.Add(Id, Position);
            if ((CollectedMask & (1 << Index)) != 0) Ledger.CollectedMasterRewards.Add(Id);
        }
    }
    if (Reader.IsError() || !ValidateMasterRewards(Ledger)) return false;
    MergeMasterLedgers(State, Ledger);
    return true;
}

bool UNLRunStateSubsystem::SaveMasterLedger(const FNLProgressionState& State)
{
    if (!bMasterLedgerAvailable || !RunId.IsValid() || !ValidateMasterRewards(State))
    {
        LastFailureReason = TEXT("InvalidMasterRewardLedger");
        return false;
    }
    TArray<uint8> Bytes;
    FMemoryWriter Writer(Bytes, true);
    uint32 Magic = MasterLedgerMagic, Version = MasterLedgerVersion;
    FGuid StoredRun = RunId;
    uint8 DefeatedMask = 0, CollectedMask = 0;
    for (int32 Index = 0; Index < 4; ++Index)
    {
        if (State.DefeatedMasterIds.Contains(MasterAt(Index))) DefeatedMask |= 1 << Index;
        if (State.CollectedMasterRewards.Contains(MasterAt(Index))) CollectedMask |= 1 << Index;
    }
    Writer << Magic << Version << StoredRun << DefeatedMask << CollectedMask;
    for (int32 Index = 0; Index < 4; ++Index)
    {
        const FVector* SavedPosition = State.MasterRewardLocations.Find(MasterAt(Index));
        const FVector Position = SavedPosition ? *SavedPosition : FVector::ZeroVector;
        double X = Position.X, Y = Position.Y, Z = Position.Z;
        Writer << X << Y << Z;
    }
    uint32 Crc = FCrc::MemCrc32(Bytes.GetData(), Bytes.Num());
    Writer << Crc;
    const FString Path = MasterLedgerPath(RunId);
    const FString Temp = Path + TEXT(".tmp");
    IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
    if (Writer.IsError() || Bytes.Num() != MasterLedgerBytes || !Files.CreateDirectoryTree(*FPaths::GetPath(Path)))
    {
        LastFailureReason = TEXT("MasterRewardLedgerWriteFailed");
        return false;
    }
    bool bWritten = false;
    {
        TUniquePtr<IFileHandle> Handle(Files.OpenWrite(*Temp, false, false));
        bWritten = Handle && Handle->Write(Bytes.GetData(), Bytes.Num()) && Handle->Flush(true);
    }
    if (!bWritten || !AtomicReplaceLedger(Path, Temp))
    {
        LastFailureReason = TEXT("MasterRewardLedgerCommitFailed");
        return false;
    }
    return true;
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
        bMasterLedgerAvailable = LoadMasterLedger(Progression);
        OnRunStateChanged.Broadcast();
    }
    LastFailureReason = bMasterLedgerAvailable ? NAME_None : FName(TEXT("MasterRewardLedgerCorrupt"));
}

bool UNLRunStateSubsystem::RestoreProgressionState(const FNLProgressionState& State)
{
    if (!RunId.IsValid() || !IsValidProgression(State))
    {
        LastFailureReason = TEXT("InvalidProgressionState");
        return false;
    }
    FNLProgressionState Candidate = State;
    // Same-run entrance reload may reset currency/waves, never first-defeat claims.
    MergeMasterLedgers(Candidate, Progression);
    if ((!Candidate.DefeatedMasterIds.IsEmpty() || !Candidate.CollectedMasterRewards.IsEmpty())
        && !SaveMasterLedger(Candidate)) return false;
    Progression = MoveTemp(Candidate);
    LastFailureReason = NAME_None;
    OnRunStateChanged.Broadcast();
    return true;
}

bool UNLRunStateSubsystem::RecordMasterDefeat(FName MasterId, FVector DropLocation)
{
    if (!RunId.IsValid() || !IsMasterId(MasterId) || DropLocation.ContainsNaN()
        || DropLocation.GetAbsMax() > 1.0e9)
    {
        LastFailureReason = TEXT("InvalidMasterDefeat");
        return false;
    }
    if (HasDefeatedMaster(MasterId)) return false;
    FNLProgressionState Candidate = Progression;
    Candidate.DefeatedMasterIds.Add(MasterId);
    Candidate.MasterRewardLocations.Add(MasterId, DropLocation);
    if (!SaveMasterLedger(Candidate)) return false;
    Progression = MoveTemp(Candidate);
    LastFailureReason = NAME_None;
    OnRunStateChanged.Broadcast();
    return true;
}

bool UNLRunStateSubsystem::CollectMasterReward(FName MasterId)
{
    if (!RunId.IsValid() || !HasDefeatedMaster(MasterId) || HasCollectedMasterReward(MasterId)) return false;
    FNLProgressionState Candidate = Progression;
    Candidate.CollectedMasterRewards.Add(MasterId);
    if (!SaveMasterLedger(Candidate)) return false;
    Progression = MoveTemp(Candidate);
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
