#include "Progression/NLOrdinaryLootSubsystem.h"

#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Encounter/NLEncounterController.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/Crc.h"
#include "Misc/Paths.h"
#include "Pickup/NLOrdinarySupplyPickup.h"
#include "Progression/NLRunStateSubsystem.h"
#include "Serialization/MemoryReader.h"
#include "Serialization/MemoryWriter.h"

#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#elif PLATFORM_LINUX || PLATFORM_MAC || PLATFORM_ANDROID || PLATFORM_IOS
#include <cstdio>
#endif

namespace
{
    constexpr uint32 LedgerMagic = 0x4E4C4F4C; // NLOL
    constexpr uint32 LedgerVersion = 1;
    constexpr int32 MaximumEvents = 4096;
    constexpr int32 MaximumBytes = 3 * 1024 * 1024;
    bool ValidEvent(FName Id)
    {
        if (Id.IsNone()) return false;
        const FString Text = Id.ToString();
        if (Text.Len() > 128) return false;
        for (TCHAR C : Text) if (!FChar::IsAlnum(C) && C != TEXT('.') && C != TEXT('_') && C != TEXT('-')) return false;
        return true;
    }
    bool ValidLocation(const FVector& Position)
    {
        return !Position.ContainsNaN() && Position.GetAbsMax() <= 1.e9;
    }
    FString LedgerPath(FGuid RunId)
    {
        return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(),
            TEXT("SaveGames/NilinOrdinaryLoot"), RunId.ToString(EGuidFormats::Digits) + TEXT(".nllo")));
    }
    bool AtomicReplace(const FString& Destination, const FString& Temp)
    {
#if PLATFORM_WINDOWS
        auto NativePath = [](FString Path)
        {
            FPaths::MakePlatformFilename(Path);
            if (!Path.StartsWith(TEXT("\\\\?\\")))
                Path = Path.StartsWith(TEXT("\\\\")) ? FString(TEXT("\\\\?\\UNC\\")) + Path.Mid(2)
                    : FString(TEXT("\\\\?\\")) + Path;
            return Path;
        };
        return !!::MoveFileExW(*NativePath(Temp), *NativePath(Destination), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
#elif PLATFORM_LINUX || PLATFORM_MAC || PLATFORM_ANDROID || PLATFORM_IOS
        return ::rename(TCHAR_TO_UTF8(*Temp), TCHAR_TO_UTF8(*Destination)) == 0;
#else
        return false;
#endif
    }
    bool CollectionPaused(UWorld* World)
    {
        if (!World || World->IsPaused()) return true;
        for (TActorIterator<ANLEncounterController> It(World); It; ++It)
            if (It->IsRunning() && It->IsEncounterPaused()) return true;
        return false;
    }
}

bool UNLOrdinaryLootSubsystem::DoesSupportWorldType(EWorldType::Type Type) const
{
    return Type == EWorldType::Game || Type == EWorldType::PIE;
}

UNLRunStateSubsystem* UNLOrdinaryLootSubsystem::ResolveRunState() const
{
    const UGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance() : nullptr;
    return GI ? GI->GetSubsystem<UNLRunStateSubsystem>() : nullptr;
}

void UNLOrdinaryLootSubsystem::BindRunState()
{
    UNLRunStateSubsystem* State = ResolveRunState();
    if (State == BoundRunState) return;
    if (BoundRunState) BoundRunState->OnRunStateChanged.RemoveDynamic(this, &ThisClass::HandleRunStateChanged);
    BoundRunState = State;
    if (BoundRunState) BoundRunState->OnRunStateChanged.AddUniqueDynamic(this, &ThisClass::HandleRunStateChanged);
}

void UNLOrdinaryLootSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    BindRunState();
    RestorePendingSupplies();
}

void UNLOrdinaryLootSubsystem::Deinitialize()
{
    if (BoundRunState) BoundRunState->OnRunStateChanged.RemoveDynamic(this, &ThisClass::HandleRunStateChanged);
    BoundRunState = nullptr;
    PendingSupplies.Reset();
    Super::Deinitialize();
}

void UNLOrdinaryLootSubsystem::ClearPendingActors()
{
    const auto Retiring = MoveTemp(PendingSupplies);
    PendingSupplies.Reset();
    for (const auto& Pair : Retiring)
        if (ANLOrdinarySupplyPickup* Pickup = Pair.Value.Get()) Pickup->Destroy();
}

bool UNLOrdinaryLootSubsystem::SynchronizeRun()
{
    BindRunState();
    const FGuid RunId = BoundRunState ? BoundRunState->GetRunId() : FGuid();
    if (!RunId.IsValid()) { LastFailureReason = TEXT("OrdinaryLootRunUnavailable"); return false; }
    if (RunId == CurrentRunId) return bLedgerAvailable;
    if (bSynchronizing) { bRefreshRequested = true; return false; }
    {
        TGuardValue<bool> SyncGuard(bSynchronizing, true);
        ClearPendingActors();
        // Destroy notifications can change the active run. Follow the latest identity.
        CurrentRunId = BoundRunState ? BoundRunState->GetRunId() : FGuid();
        if (!CurrentRunId.IsValid()) { LastFailureReason = TEXT("OrdinaryLootRunUnavailable"); return false; }
        Records.Reset();
        Probability = .2f;
        RandomState = static_cast<int32>(FCrc::MemCrc32(&CurrentRunId, sizeof(CurrentRunId)));
        ConsecutiveMisses = 0;
        LastCollectedHealth = 0;
        LastCollectedTimeSeconds = -1000;
        bLedgerAvailable = LoadLedger();
    }
    if (bRefreshRequested && !bRefreshing && bLedgerAvailable) RestorePendingSupplies();
    return bLedgerAvailable;
}

void UNLOrdinaryLootSubsystem::HandleRunStateChanged()
{
    // Growth and energy updates broadcast this delegate frequently. No same-run IO or actor scan.
    if (BoundRunState && BoundRunState->GetRunId() == CurrentRunId) return;
    RestorePendingSupplies();
}

bool UNLOrdinaryLootSubsystem::LoadLedger()
{
    IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
    const FString Path = LedgerPath(CurrentRunId);
    LastFailureReason = NAME_None;
    if (!Files.FileExists(*Path)) return true;
    auto Corrupt = [this]() { LastFailureReason = TEXT("OrdinaryLootLedgerCorrupt"); return false; };
    TUniquePtr<IFileHandle> Handle(Files.OpenRead(*Path));
    if (!Handle || Handle->Size() < 44 || Handle->Size() > MaximumBytes) return Corrupt();
    TArray<uint8> Bytes;
    Bytes.SetNumUninitialized(static_cast<int32>(Handle->Size()));
    if (!Handle->Read(Bytes.GetData(), Bytes.Num())) return Corrupt();
    uint32 ExpectedCrc = 0;
    FMemory::Memcpy(&ExpectedCrc, Bytes.GetData() + Bytes.Num() - 4, 4);
    if (ExpectedCrc != FCrc::MemCrc32(Bytes.GetData(), Bytes.Num() - 4)) return Corrupt();
    FMemoryReader Reader(Bytes, true);
    uint32 Magic = 0, Version = 0;
    FGuid Run;
    int32 Seed = 0, Misses = 0, Count = 0;
    float LoadedProbability = 0;
    Reader << Magic << Version << Run << Seed << LoadedProbability << Misses << Count;
    if (Magic != LedgerMagic || Version != LedgerVersion || Run != CurrentRunId || Count < 0 || Count > MaximumEvents
        || Misses < 0 || Misses > 4 || !FMath::IsFinite(LoadedProbability) || LoadedProbability < 0 || LoadedProbability > 1) return Corrupt();
    TArray<FRecord> Loaded;
    TSet<FName> Seen;
    int32 VerifiedMisses = 0;
    for (int32 Index = 0; Index < Count; ++Index)
    {
        uint16 Length = 0;
        Reader << Length;
        if (Reader.IsError() || Length == 0 || Length > 512 || Reader.Tell() + Length + 26 > Bytes.Num() - 4) return Corrupt();
        TArray<ANSICHAR> Name;
        Name.SetNumUninitialized(Length);
        Reader.Serialize(Name.GetData(), Length);
        FUTF8ToTCHAR Converted(Name.GetData(), Length);
        FRecord Record;
        Record.EventId = FName(*FString(Converted.Length(), Converted.Get()));
        uint8 Kind = 0, Claimed = 0;
        Reader << Kind << Claimed << Record.Location.X << Record.Location.Y << Record.Location.Z;
        if (Reader.IsError() || !ValidEvent(Record.EventId) || Seen.Contains(Record.EventId) || !ValidLocation(Record.Location)
            || Kind > static_cast<uint8>(ENLOrdinarySupplyKind::Large) || Claimed > 1 || (Kind == 0 && Claimed != 0)) return Corrupt();
        Record.Kind = static_cast<ENLOrdinarySupplyKind>(Kind);
        Record.bCollected = Claimed != 0;
        VerifiedMisses = Kind == 0 ? VerifiedMisses + 1 : 0;
        if (VerifiedMisses > 4) return Corrupt();
        Seen.Add(Record.EventId);
        Loaded.Add(Record);
    }
    if (Reader.IsError() || Reader.Tell() != Bytes.Num() - 4 || Misses != VerifiedMisses) return Corrupt();
    Records = MoveTemp(Loaded);
    Probability = LoadedProbability;
    RandomState = Seed;
    ConsecutiveMisses = Misses;
    return true;
}

bool UNLOrdinaryLootSubsystem::CommitLedger(const TArray<FRecord>& Candidate, int32 CandidateMisses, int32 CandidateSeed)
{
    if (!bLedgerAvailable || !CurrentRunId.IsValid() || Candidate.Num() > MaximumEvents)
    { LastFailureReason = TEXT("InvalidOrdinaryLootLedger"); return false; }
    TArray<uint8> Bytes;
    FMemoryWriter Writer(Bytes, true);
    uint32 Magic = LedgerMagic, Version = LedgerVersion;
    FGuid Run = CurrentRunId;
    int32 Count = Candidate.Num();
    float SavedProbability = Probability;
    Writer << Magic << Version << Run << CandidateSeed << SavedProbability << CandidateMisses << Count;
    for (const FRecord& Record : Candidate)
    {
        const FTCHARToUTF8 Utf8(*Record.EventId.ToString());
        uint16 Length = static_cast<uint16>(Utf8.Length());
        Writer << Length;
        Writer.Serialize(const_cast<ANSICHAR*>(Utf8.Get()), Length);
        uint8 Kind = static_cast<uint8>(Record.Kind), Claimed = Record.bCollected ? 1 : 0;
        double X = Record.Location.X, Y = Record.Location.Y, Z = Record.Location.Z;
        Writer << Kind << Claimed << X << Y << Z;
    }
    uint32 Crc = FCrc::MemCrc32(Bytes.GetData(), Bytes.Num());
    Writer << Crc;
    IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
    const FString Path = LedgerPath(CurrentRunId), Temp = Path + TEXT(".tmp");
    if (Writer.IsError() || Bytes.Num() > MaximumBytes || !Files.CreateDirectoryTree(*FPaths::GetPath(Path)))
    { LastFailureReason = TEXT("OrdinaryLootLedgerWriteFailed"); return false; }
    bool bWritten = false;
    {
        TUniquePtr<IFileHandle> Handle(Files.OpenWrite(*Temp, false, false));
        bWritten = Handle && Handle->Write(Bytes.GetData(), Bytes.Num()) && Handle->Flush(true);
    }
    if (!bWritten || !AtomicReplace(Path, Temp))
    { LastFailureReason = TEXT("OrdinaryLootLedgerCommitFailed"); return false; }
    Records = Candidate;
    ConsecutiveMisses = CandidateMisses;
    RandomState = CandidateSeed;
    LastFailureReason = NAME_None;
    return true;
}

float UNLOrdinaryLootSubsystem::HealthForKind(ENLOrdinarySupplyKind Kind)
{
    return Kind == ENLOrdinarySupplyKind::Small ? 10.0f : Kind == ENLOrdinarySupplyKind::Large ? 20.0f : 0.0f;
}

ENLOrdinarySupplyKind UNLOrdinaryLootSubsystem::EvaluateRoll(float DropRoll, float SizeRoll, int32 Misses, float DropProbability)
{
    if (Misses < 4 && DropRoll >= DropProbability) return ENLOrdinarySupplyKind::None;
    return SizeRoll < .8f ? ENLOrdinarySupplyKind::Small : ENLOrdinarySupplyKind::Large;
}

bool UNLOrdinaryLootSubsystem::ConfigureDropRules(float DropProbability, int32 RandomSeed)
{
    if (!SynchronizeRun()) return false;
    if (!Records.IsEmpty() || !FMath::IsFinite(DropProbability) || DropProbability < 0 || DropProbability > 1)
    { LastFailureReason = TEXT("OrdinaryLootRulesLockedOrInvalid"); return false; }
    Probability = DropProbability;
    RandomState = RandomSeed;
    LastFailureReason = NAME_None;
    return true;
}

const UNLOrdinaryLootSubsystem::FRecord* UNLOrdinaryLootSubsystem::FindRecord(FName Id) const
{
    return Records.FindByPredicate([Id](const FRecord& Record) { return Record.EventId == Id; });
}

bool UNLOrdinaryLootSubsystem::HasProcessedEvent(FName Id) const { return FindRecord(Id) != nullptr; }
bool UNLOrdinaryLootSubsystem::HasCollectedSupply(FName Id) const
{
    const FRecord* Record = FindRecord(Id);
    return Record && Record->bCollected;
}
ENLOrdinarySupplyKind UNLOrdinaryLootSubsystem::GetSupplyKind(FName Id) const
{
    const FRecord* Record = FindRecord(Id);
    return Record ? Record->Kind : ENLOrdinarySupplyKind::None;
}

bool UNLOrdinaryLootSubsystem::RecordEligibleDefeat(FName Id, FVector Location)
{
    if (!ValidEvent(Id) || !ValidLocation(Location))
    { LastFailureReason = TEXT("InvalidOrdinaryLootEvent"); return false; }
    const UNLRunStateSubsystem* StartingState = ResolveRunState();
    const FGuid StartingRun = StartingState ? StartingState->GetRunId() : FGuid();
    if (CollectionPaused(GetWorld()) || bClaiming || !SynchronizeRun()) return false;
    if (CurrentRunId != StartingRun) { LastFailureReason = TEXT("OrdinaryLootRunChanged"); return false; }
    if (const FRecord* Existing = FindRecord(Id))
    {
        if (Existing->Kind != ENLOrdinarySupplyKind::None && !Existing->bCollected) CreatePendingSupply(*Existing);
        LastFailureReason = NAME_None;
        return true;
    }
    if (Records.Num() >= MaximumEvents) { LastFailureReason = TEXT("OrdinaryLootEventLimit"); return false; }
    FRandomStream Random(RandomState);
    const float DropRoll = Random.FRand();
    const bool bDrops = ConsecutiveMisses >= 4 || DropRoll < Probability;
    const float SizeRoll = bDrops ? Random.FRand() : 0;
    FRecord Record;
    Record.EventId = Id;
    Record.Location = Location;
    Record.Kind = EvaluateRoll(DropRoll, SizeRoll, ConsecutiveMisses, Probability);
    TArray<FRecord> Candidate = Records;
    Candidate.Add(Record);
    if (!CommitLedger(Candidate, bDrops ? 0 : ConsecutiveMisses + 1, Random.GetCurrentSeed())) return false;
    if (bDrops) CreatePendingSupply(Record);
    return true;
}

ANLOrdinarySupplyPickup* UNLOrdinaryLootSubsystem::GetPendingSupply(FName Id) const
{
    const TWeakObjectPtr<ANLOrdinarySupplyPickup>* Found = PendingSupplies.Find(Id);
    ANLOrdinarySupplyPickup* Pickup = Found ? Found->Get() : nullptr;
    return IsValid(Pickup) && !Pickup->IsActorBeingDestroyed() ? Pickup : nullptr;
}

TArray<ANLOrdinarySupplyPickup*> UNLOrdinaryLootSubsystem::GetPendingSupplies() const
{
    TArray<ANLOrdinarySupplyPickup*> Result;
    for (const auto& Pair : PendingSupplies)
        if (ANLOrdinarySupplyPickup* Pickup = GetPendingSupply(Pair.Key)) Result.Add(Pickup);
    return Result;
}

ANLOrdinarySupplyPickup* UNLOrdinaryLootSubsystem::CreatePendingSupply(const FRecord& Record)
{
    if (Record.Kind == ENLOrdinarySupplyKind::None || Record.bCollected || !GetWorld()) return nullptr;
    if (ANLOrdinarySupplyPickup* Existing = GetPendingSupply(Record.EventId)) return Existing;
    // Copy everything before FinishSpawning: an automatic overlap can claim it synchronously.
    const FRecord Copy = Record;
    const FGuid SpawnRun = CurrentRunId;
    ANLOrdinarySupplyPickup* Pickup = GetWorld()->SpawnActorDeferred<ANLOrdinarySupplyPickup>(
        ANLOrdinarySupplyPickup::StaticClass(), FTransform(Copy.Location), nullptr, nullptr,
        ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (!Pickup) return nullptr;
    if (!Pickup->InitializeSupply(Copy.EventId, SpawnRun, HealthForKind(Copy.Kind)))
    { Pickup->Destroy(); return nullptr; }
    PendingSupplies.Add(Copy.EventId, Pickup);
    Pickup->FinishSpawning(FTransform(Copy.Location));
    return IsValid(Pickup) && !Pickup->IsActorBeingDestroyed() ? Pickup : nullptr;
}

void UNLOrdinaryLootSubsystem::RestorePendingSupplies()
{
    if (bRefreshing || bSynchronizing) { bRefreshRequested = true; return; }
    if (!GetWorld()) return;
    // FinishSpawning can synchronously collect a supply and begin a different run.
    // Repeat after the guard is released rather than retaining the prior run's actors.
    for (int32 Pass = 0; Pass < 4; ++Pass)
    {
        bRefreshRequested = false;
        {
            TGuardValue<bool> Guard(bRefreshing, true);
            if (!SynchronizeRun()) return;
            const FGuid RestoreRun = CurrentRunId;
            TArray<FName> Retiring;
            for (const auto& Pair : PendingSupplies)
            {
                const FRecord* Record = FindRecord(Pair.Key);
                ANLOrdinarySupplyPickup* Pickup = Pair.Value.Get();
                if (!Record || Record->bCollected || Record->Kind == ENLOrdinarySupplyKind::None
                    || !IsValid(Pickup) || Pickup->IsActorBeingDestroyed()) Retiring.Add(Pair.Key);
            }
            for (FName Id : Retiring)
            {
                const TWeakObjectPtr<ANLOrdinarySupplyPickup> Pickup = PendingSupplies.FindRef(Id);
                PendingSupplies.Remove(Id);
                if (Pickup.IsValid()) Pickup->Destroy();
                if (!BoundRunState || BoundRunState->GetRunId() != RestoreRun) break;
            }
            const TArray<FRecord> Copy = Records;
            for (const FRecord& Record : Copy)
            {
                if (!BoundRunState || BoundRunState->GetRunId() != RestoreRun) { bRefreshRequested = true; break; }
                if (Record.Kind != ENLOrdinarySupplyKind::None && !Record.bCollected) CreatePendingSupply(Record);
            }
        }
        if (!bRefreshRequested) break;
    }
}

bool UNLOrdinaryLootSubsystem::TryCollect(FName Id, AActor* Collector)
{
    // The initiating pickup belongs to the currently displayed run. A deferred
    // run refresh cannot turn its old event ID into a claim on the new run.
    const FGuid StartingRun = CurrentRunId;
    if (bClaiming || CollectionPaused(GetWorld()) || !IsValid(Collector) || Collector->GetWorld() != GetWorld()
        || !SynchronizeRun()) return false;
    if (CurrentRunId != StartingRun) return false;
    const UNLCombatIdentityComponent* Identity = Collector->FindComponentByClass<UNLCombatIdentityComponent>();
    UNLCombatVitalsComponent* Vitals = Collector->FindComponentByClass<UNLCombatVitalsComponent>();
    const FRecord* Record = FindRecord(Id);
    if (!Identity || Identity->GetFaction() != ENLCombatFaction::Player || !Vitals || Vitals->IsDead()
        || !FMath::IsFinite(Vitals->GetHealth()) || !FMath::IsFinite(Vitals->GetMaxHealth())
        || Vitals->GetHealth() >= Vitals->GetMaxHealth() || !Record || Record->bCollected
        || Record->Kind == ENLOrdinarySupplyKind::None) return false;
    TGuardValue<bool> ClaimGuard(bClaiming, true);
    const float Health = HealthForKind(Record->Kind);
    TArray<FRecord> Candidate = Records;
    Candidate.FindByPredicate([Id](const FRecord& R) { return R.EventId == Id; })->bCollected = true;
    if (!CommitLedger(Candidate, ConsecutiveMisses, RandomState)) return false;
    // No synchronous delegate is emitted between the durable commit and this health grant.
    const FGuid ClaimRun = CurrentRunId;
    const TWeakObjectPtr<ANLOrdinarySupplyPickup> Pickup = GetPendingSupply(Id);
    PendingSupplies.Remove(Id);
    const float Restored = Vitals->RestoreHealth(Health);
    if (Pickup.IsValid()) Pickup->Destroy();
    if (CurrentRunId == ClaimRun && BoundRunState && BoundRunState->GetRunId() == ClaimRun)
    {
        LastCollectedHealth = Restored;
        LastCollectedTimeSeconds = GetWorld()->GetTimeSeconds();
    }
    return Restored > 0;
}
