#include "Save/NLCheckpointService.h"

#include "Save/NLCheckpointSaveGame.h"
#include "Progression/NLRunStateSubsystem.h"
#include "HAL/PlatformFileManager.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/Crc.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "Serialization/MemoryReader.h"
#include "Serialization/MemoryWriter.h"

#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#elif PLATFORM_LINUX || PLATFORM_MAC || PLATFORM_ANDROID || PLATFORM_IOS
#include <cstdio>
#endif

namespace NLCheckpoint
{
    constexpr uint32 EnvelopeMagic = 0x4E4C4350; // NLCP
    constexpr uint32 EnvelopeVersion = 1;
    constexpr uint32 SnapshotBodyMagic = 0x4E4C5331; // NLS1
    constexpr int32 SnapshotVersion = 2;
    constexpr int32 EnvelopeHeaderBytes = 4 * sizeof(uint32);
    constexpr int32 MaxPayloadBytes = 4 * 1024 * 1024;
    constexpr int32 MaxIdCharacters = 128;
    constexpr int32 MaxWaveIds = 1024;
    constexpr int32 MaxRewardIds = 4096;
    constexpr int32 MaxMilestoneIds = 1024;
    constexpr int32 MaxInterferenceIds = 1024;

    struct FCheckpointPaths
    {
        FString Directory = FPaths::ConvertRelativePathToFull(
            FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("SaveGames"), TEXT("NilinCheckpoint")));
        FString Primary = FPaths::Combine(Directory, TEXT("Checkpoint.current.nlcp"));
        FString Backup = FPaths::Combine(Directory, TEXT("Checkpoint.backup.nlcp"));
        FString PrimaryTemp = FPaths::Combine(Directory, TEXT("Checkpoint.current.tmp"));
        FString BackupTemp = FPaths::Combine(Directory, TEXT("Checkpoint.backup.tmp"));

        FCheckpointPaths(FName LevelId, FName EncounterId, FName ContentRevision, const TArray<FName>& WaveIds)
        {
            // Keep the previously delivered checkpoint lab's existing slot intact.
            const bool bLegacyLab = LevelId == TEXT("Level.CombatLab.Checkpoint")
                && EncounterId == TEXT("Encounter.SwordWaves") && ContentRevision == TEXT("SwordWaves.SAVE01.1")
                && WaveIds.Num() == 2 && WaveIds[0] == TEXT("Wave.Sword.01") && WaveIds[1] == TEXT("Wave.Sword.02");
            if (bLegacyLab) return;
            FString Key;
            auto AddId = [&Key](FName Id)
            {
                const FString Text = Id.ToString().ToLower();
                Key += FString::Printf(TEXT("%d:%s"), Text.Len(), *Text);
            };
            AddId(LevelId);
            AddId(EncounterId);
            AddId(ContentRevision);
            for (FName WaveId : WaveIds) AddId(WaveId);
            const FTCHARToUTF8 Encoded(*Key);
            FSHAHash Hash;
            FSHA1::HashBuffer(Encoded.Get(), Encoded.Length(), Hash.Hash);
            const FString Prefix = TEXT("Checkpoint.") + Hash.ToString();
            Primary = FPaths::Combine(Directory, Prefix + TEXT(".current.nlcp"));
            Backup = FPaths::Combine(Directory, Prefix + TEXT(".backup.nlcp"));
            PrimaryTemp = FPaths::Combine(Directory, Prefix + TEXT(".current.tmp"));
            BackupTemp = FPaths::Combine(Directory, Prefix + TEXT(".backup.tmp"));
        }
    };

    bool IsStableId(FName Id, bool bAllowNone = false)
    {
        return (bAllowNone && Id.IsNone()) || (!Id.IsNone() && Id.ToString().Len() <= MaxIdCharacters);
    }

    bool ValidateIds(const TArray<FName>& Ids, int32 Maximum, bool bRequireNonEmpty = false)
    {
        if (Ids.Num() > Maximum || (bRequireNonEmpty && Ids.IsEmpty()))
        {
            return false;
        }
        TSet<FName> Seen;
        for (FName Id : Ids)
        {
            if (!IsStableId(Id) || Seen.Contains(Id))
            {
                return false;
            }
            Seen.Add(Id);
        }
        return true;
    }

    bool IsFiniteRange(double Value, double Minimum, double Maximum)
    {
        return FMath::IsFinite(Value) && Value >= Minimum && Value <= Maximum;
    }

    bool CanRead(FArchive& Ar, int64 ByteCount)
    {
        const int64 Position = Ar.Tell();
        const int64 Size = Ar.TotalSize();
        if (Ar.IsError() || ByteCount < 0 || Position < 0 || Size < Position || ByteCount > Size - Position)
        {
            Ar.SetError();
            return false;
        }
        return true;
    }

    // Check FString's signed character count before the engine can allocate from it.
    bool SerializeBoundedString(FArchive& Ar, FString& Value, int32 MaxCharacters)
    {
        if (Ar.IsLoading())
        {
            if (!CanRead(Ar, sizeof(int32)))
            {
                return false;
            }
            const int64 Start = Ar.Tell();
            int32 SignedCount = 0;
            Ar << SignedCount;
            const int64 CharacterCount = SignedCount < 0 ? -static_cast<int64>(SignedCount) : SignedCount;
            const int64 ByteCount = CharacterCount * (SignedCount < 0 ? sizeof(UTF16CHAR) : sizeof(ANSICHAR));
            if (CharacterCount > MaxCharacters + 1 || !CanRead(Ar, ByteCount))
            {
                Ar.SetError();
                return false;
            }
            Ar.Seek(Start);
        }
        else if (Value.Len() > MaxCharacters)
        {
            Ar.SetError();
            return false;
        }
        Ar << Value;
        return !Ar.IsError() && Value.Len() <= MaxCharacters;
    }

    bool SerializeId(FArchive& Ar, FName& Id)
    {
        FString Text = Ar.IsSaving() ? Id.ToString() : FString();
        if (!SerializeBoundedString(Ar, Text, MaxIdCharacters))
        {
            return false;
        }
        if (Ar.IsLoading())
        {
            Id = FName(*Text);
        }
        return true;
    }

    bool SerializeIds(FArchive& Ar, TArray<FName>& Ids, int32 Maximum)
    {
        int32 Count = Ar.IsSaving() ? Ids.Num() : 0;
        Ar << Count;
        if (Ar.IsError() || Count < 0 || Count > Maximum)
        {
            Ar.SetError();
            return false;
        }
        if (Ar.IsLoading())
        {
            // Every serialized ID includes at least its four-byte string count.
            if (!CanRead(Ar, static_cast<int64>(Count) * sizeof(int32)))
            {
                return false;
            }
            Ids.SetNum(Count);
        }
        for (FName& Id : Ids)
        {
            if (!SerializeId(Ar, Id))
            {
                return false;
            }
        }
        return true;
    }

    bool SerializeSnapshot(FArchive& Ar, FNLCheckpointSnapshot& Snapshot, FName& Failure)
    {
        uint32 BodyMagic = SnapshotBodyMagic;
        // Always write the latest schema; version-one entrances remain readable.
        if (Ar.IsSaving()) Snapshot.SaveVersion = SnapshotVersion;
        Ar << BodyMagic;
        Ar << Snapshot.SaveVersion;
        if (Ar.IsError() || BodyMagic != SnapshotBodyMagic)
        {
            Failure = TEXT("InvalidSnapshotPayload");
            Ar.SetError();
            return false;
        }
        if (Snapshot.SaveVersion != 1 && Snapshot.SaveVersion != SnapshotVersion)
        {
            Failure = TEXT("UnsupportedSaveVersion");
            Ar.SetError();
            return false;
        }
        if (!SerializeId(Ar, Snapshot.ContentRevision)) { return false; }
        Ar << Snapshot.RunId;
        if (!SerializeId(Ar, Snapshot.LevelId) || !SerializeId(Ar, Snapshot.NodeId)
            || !SerializeId(Ar, Snapshot.EncounterId) || !SerializeId(Ar, Snapshot.CheckpointId)
            || !SerializeIds(Ar, Snapshot.OrderedWaveIds, MaxWaveIds)) { return false; }
        Ar << Snapshot.WaveOrBossPhaseIndex;
        Ar << Snapshot.WaveInitialSeed;
        Ar << Snapshot.WaveRandomState;

        const FVector Translation = Snapshot.EntryTransform.GetTranslation();
        const FQuat Rotation = Snapshot.EntryTransform.GetRotation();
        const FVector Scale = Snapshot.EntryTransform.GetScale3D();
        double TransformValues[10] = { Translation.X, Translation.Y, Translation.Z,
            Rotation.X, Rotation.Y, Rotation.Z, Rotation.W, Scale.X, Scale.Y, Scale.Z };
        for (double& Value : TransformValues) { Ar << Value; }
        if (Ar.IsLoading() && !Ar.IsError())
        {
            // Reject raw NaN/Inf before FTransform's diagnostics can replace them.
            for (double Value : TransformValues)
            {
                if (!FMath::IsFinite(Value))
                {
                    Failure = TEXT("InvalidEntryTransform");
                    Ar.SetError();
                    return false;
                }
            }
            Snapshot.EntryTransform = FTransform(
                FQuat(TransformValues[3], TransformValues[4], TransformValues[5], TransformValues[6]),
                FVector(TransformValues[0], TransformValues[1], TransformValues[2]),
                FVector(TransformValues[7], TransformValues[8], TransformValues[9]));
        }
        Ar << Snapshot.EntryControlRotation.Pitch;
        Ar << Snapshot.EntryControlRotation.Yaw;
        Ar << Snapshot.EntryControlRotation.Roll;
        Ar << Snapshot.PlayerResourcePreset.Health;
        Ar << Snapshot.PlayerResourcePreset.Guard;
        Ar << Snapshot.ProgressionState.LingQi;
        Ar << Snapshot.ProgressionState.BurstEnergy;
        Ar << Snapshot.ProgressionState.UpgradeLevel;
        if (!SerializeIds(Ar, Snapshot.ProgressionState.RewardedEventIds, MaxRewardIds)
            || !SerializeId(Ar, Snapshot.ObjectiveState.StableId)) { return false; }
        Ar << Snapshot.ObjectiveState.Integrity;
        Ar << Snapshot.ObjectiveState.RescueProgress;
        uint8 Completed = Snapshot.ObjectiveState.bCompleted ? 1 : 0;
        Ar << Completed;
        if (Completed > 1)
        {
            Ar.SetError();
            return false;
        }
        if (Ar.IsLoading()) { Snapshot.ObjectiveState.bCompleted = Completed != 0; }
        if (!SerializeIds(Ar, Snapshot.ObjectiveState.InterferenceSourceIds, MaxInterferenceIds)
            || !SerializeIds(Ar, Snapshot.CompletedMilestones, MaxMilestoneIds)) { return false; }
        if (Snapshot.SaveVersion >= 2)
        {
            if (!SerializeIds(Ar, Snapshot.ProgressionState.DefeatedMasterIds, 4)
                || !SerializeIds(Ar, Snapshot.ProgressionState.CollectedMasterRewards, 4)) return false;
            if (Ar.IsLoading()) Snapshot.ProgressionState.MasterRewardLocations.Reset();
            for (FName MasterId : Snapshot.ProgressionState.DefeatedMasterIds)
            {
                FVector Position = Ar.IsSaving()
                    ? Snapshot.ProgressionState.MasterRewardLocations.FindRef(MasterId) : FVector::ZeroVector;
                double X = Position.X, Y = Position.Y, Z = Position.Z;
                Ar << X << Y << Z;
                if (Ar.IsLoading()) Snapshot.ProgressionState.MasterRewardLocations.Add(MasterId, FVector(X, Y, Z));
            }
        }
        if (Ar.IsError() || (Ar.IsLoading() && Ar.Tell() != Ar.TotalSize()))
        {
            Ar.SetError();
            return false;
        }
        return UNLCheckpointService::ValidateSnapshot(Snapshot, Failure);
    }

    // Authoritative UE 5.8 GameplayStatics.cpp writes v3 with optimized GUID versions.
    // Preflight all variable lengths and the exact native class before LoadGameFromMemory.
    bool ValidateEngineHeader(const TArray<uint8>& Payload, FName& Failure)
    {
        FMemoryReader Reader(Payload, true);
        int32 Tag = 0;
        int32 HeaderVersion = 0;
        int32 UE4Version = 0;
        int32 UE5Version = 0;
        uint16 Major = 0, Minor = 0, Patch = 0;
        uint32 Changelist = 0;
        Reader << Tag << HeaderVersion << UE4Version << UE5Version;
        Reader << Major << Minor << Patch << Changelist;
        if (Reader.IsError() || Tag != 0x53415647 || HeaderVersion != 3)
        {
            Failure = TEXT("UnsupportedEngineSaveHeader");
            return false;
        }
        FString Branch;
        if (!SerializeBoundedString(Reader, Branch, 512))
        {
            Failure = TEXT("InvalidEngineSaveHeader");
            return false;
        }
        int32 CustomFormat = 0, CustomCount = 0;
        Reader << CustomFormat << CustomCount;
        const int64 CustomBytes = static_cast<int64>(CustomCount) * (sizeof(uint32) * 4 + sizeof(int32));
        if (Reader.IsError() || CustomFormat != 3 || CustomCount < 0 || CustomCount > 4096
            || !CanRead(Reader, CustomBytes))
        {
            Failure = TEXT("InvalidEngineSaveHeader");
            return false;
        }
        Reader.Seek(Reader.Tell() + CustomBytes);
        FString ClassPath;
        if (!SerializeBoundedString(Reader, ClassPath, 256))
        {
            Failure = TEXT("InvalidEngineSaveHeader");
            return false;
        }
        if (ClassPath != UNLCheckpointSaveGame::StaticClass()->GetPathName())
        {
            Failure = TEXT("UnexpectedSaveGameClass");
            return false;
        }
        if (!CanRead(Reader, sizeof(uint32) + sizeof(int32)))
        {
            Failure = TEXT("InvalidSnapshotPayload");
            return false;
        }
        return true;
    }

    bool DecodeEnvelope(const TArray<uint8>& Bytes, FNLCheckpointSnapshot& OutSnapshot, FName& Failure)
    {
        if (Bytes.Num() < EnvelopeHeaderBytes || Bytes.Num() > MaxPayloadBytes + EnvelopeHeaderBytes)
        {
            Failure = TEXT("InvalidEnvelopeSize");
            return false;
        }
        FMemoryReader Reader(Bytes, true);
        uint32 Magic = 0, Version = 0, PayloadLength = 0, PayloadCrc = 0;
        Reader << Magic << Version << PayloadLength << PayloadCrc;
        if (Reader.IsError() || Magic != EnvelopeMagic)
        {
            Failure = TEXT("InvalidEnvelopeMagic");
            return false;
        }
        if (Version != EnvelopeVersion)
        {
            Failure = TEXT("UnsupportedEnvelopeVersion");
            return false;
        }
        if (PayloadLength == 0 || PayloadLength > MaxPayloadBytes
            || PayloadLength != static_cast<uint32>(Bytes.Num() - EnvelopeHeaderBytes))
        {
            Failure = TEXT("InvalidEnvelopeLength");
            return false;
        }
        const uint8* PayloadStart = Bytes.GetData() + EnvelopeHeaderBytes;
        if (FCrc::MemCrc32(PayloadStart, PayloadLength) != PayloadCrc)
        {
            Failure = TEXT("EnvelopeChecksumMismatch");
            return false;
        }
        TArray<uint8> Payload;
        Payload.Append(PayloadStart, static_cast<int32>(PayloadLength));
        if (!ValidateEngineHeader(Payload, Failure)) { return false; }
        USaveGame* LoadedObject = UGameplayStatics::LoadGameFromMemory(Payload);
        if (!LoadedObject || LoadedObject->GetClass() != UNLCheckpointSaveGame::StaticClass())
        {
            Failure = TEXT("UnexpectedSaveGameClass");
            return false;
        }
        const UNLCheckpointSaveGame* Save = Cast<UNLCheckpointSaveGame>(LoadedObject);
        if (!Save->WasSerializationValid())
        {
            Failure = Save->GetSerializationFailureReason();
            return false;
        }
        if (!UNLCheckpointService::ValidateSnapshot(Save->Snapshot, Failure)) { return false; }
        OutSnapshot = Save->Snapshot;
        Failure = NAME_None;
        return true;
    }

    bool ReadCheckpointFile(const FString& Path, FNLCheckpointSnapshot& OutSnapshot,
        TArray<uint8>& OutBytes, FName& Failure)
    {
        IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
        if (!Files.FileExists(*Path))
        {
            Failure = TEXT("CheckpointMissing");
            return false;
        }
        TUniquePtr<IFileHandle> Handle(Files.OpenRead(*Path));
        if (!Handle)
        {
            Failure = TEXT("CheckpointReadFailed");
            return false;
        }
        const int64 Size = Handle->Size();
        if (Size < EnvelopeHeaderBytes || Size > MaxPayloadBytes + EnvelopeHeaderBytes)
        {
            Failure = TEXT("InvalidEnvelopeSize");
            return false;
        }
        TArray<uint8> Bytes;
        Bytes.SetNumUninitialized(static_cast<int32>(Size));
        if (!Handle->Read(Bytes.GetData(), Size))
        {
            Failure = TEXT("CheckpointReadFailed");
            return false;
        }
        if (!DecodeEnvelope(Bytes, OutSnapshot, Failure)) { return false; }
        OutBytes = MoveTemp(Bytes);
        return true;
    }

    bool BuildEnvelope(const FNLCheckpointSnapshot& Snapshot, TArray<uint8>& OutBytes, FName& Failure)
    {
        UNLCheckpointSaveGame* Save = NewObject<UNLCheckpointSaveGame>();
        Save->Snapshot = Snapshot;
        TArray<uint8> Payload;
        if (!UGameplayStatics::SaveGameToMemory(Save, Payload) || !Save->WasSerializationValid())
        {
            Failure = Save->GetSerializationFailureReason().IsNone()
                ? FName(TEXT("CheckpointSerializeFailed")) : Save->GetSerializationFailureReason();
            return false;
        }
        if (Payload.IsEmpty() || Payload.Num() > MaxPayloadBytes)
        {
            Failure = TEXT("CheckpointPayloadTooLarge");
            return false;
        }
        FMemoryWriter Writer(OutBytes, true);
        uint32 Magic = EnvelopeMagic, Version = EnvelopeVersion;
        uint32 Length = static_cast<uint32>(Payload.Num());
        uint32 Crc = FCrc::MemCrc32(Payload.GetData(), Payload.Num());
        Writer << Magic << Version << Length << Crc;
        Writer.Serialize(Payload.GetData(), Payload.Num());
        if (Writer.IsError())
        {
            Failure = TEXT("CheckpointSerializeFailed");
            return false;
        }
        return true;
    }

    bool WriteFlushedTemp(const FString& Path, const TArray<uint8>& Bytes)
    {
        IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
        TUniquePtr<IFileHandle> Handle(Files.OpenWrite(*Path, false, false));
        return Handle && Handle->Write(Bytes.GetData(), Bytes.Num()) && Handle->Flush(true);
    }

    bool AtomicReplace(const FString& Destination, const FString& Temp)
    {
#if PLATFORM_WINDOWS
        auto NativePath = [](const FString& Path)
        {
            FString Native = FPaths::ConvertRelativePathToFull(Path);
            FPaths::MakePlatformFilename(Native);
            // Native Windows calls need an extended prefix for long project directories.
            if (!Native.StartsWith(TEXT("\\\\?\\")))
            {
                Native = Native.StartsWith(TEXT("\\\\"))
                    ? FString(TEXT("\\\\?\\UNC\\")) + Native.Mid(2)
                    : FString(TEXT("\\\\?\\")) + Native;
            }
            return Native;
        };
        const FString NativeDestination = NativePath(Destination);
        const FString NativeTemp = NativePath(Temp);
        return !!::MoveFileExW(*NativeTemp, *NativeDestination, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
#elif PLATFORM_LINUX || PLATFORM_MAC || PLATFORM_ANDROID || PLATFORM_IOS
        // Both names are in the same directory, so POSIX rename replaces atomically.
        return ::rename(TCHAR_TO_UTF8(*Temp), TCHAR_TO_UTF8(*Destination)) == 0;
#else
        // Do not fall back to IFileManager::Move: it deletes the destination first.
        return false;
#endif
    }

    bool MatchesContent(const FNLCheckpointSnapshot& Snapshot, FName LevelId, FName EncounterId,
        FName ContentRevision, const TArray<FName>& OrderedWaveIds, FName& Failure)
    {
        if (Snapshot.LevelId != LevelId) { Failure = TEXT("CheckpointLevelMismatch"); return false; }
        if (Snapshot.EncounterId != EncounterId) { Failure = TEXT("CheckpointEncounterMismatch"); return false; }
        if (Snapshot.ContentRevision != ContentRevision) { Failure = TEXT("CheckpointContentRevisionMismatch"); return false; }
        if (Snapshot.OrderedWaveIds != OrderedWaveIds) { Failure = TEXT("CheckpointWaveIdsMismatch"); return false; }
        return true;
    }
}

void UNLCheckpointSaveGame::Serialize(FArchive& Ar)
{
    if (!Ar.IsPersistent() || (!Ar.IsSaving() && !Ar.IsLoading()))
    {
        Super::Serialize(Ar);
        return;
    }
    // Dedicated save object: bounded primitive fields replace reflected property allocation.
    SerializationFailureReason = NAME_None;
    bSerializationValid = NLCheckpoint::SerializeSnapshot(Ar, Snapshot, SerializationFailureReason);
    if (!bSerializationValid && SerializationFailureReason.IsNone())
    {
        SerializationFailureReason = TEXT("InvalidSnapshotPayload");
    }
}

bool UNLCheckpointService::ValidateSnapshot(const FNLCheckpointSnapshot& Snapshot, FName& OutFailureReason)
{
    using namespace NLCheckpoint;
    auto Fail = [&OutFailureReason](const TCHAR* Reason) { OutFailureReason = FName(Reason); return false; };
    if (Snapshot.SaveVersion != 1 && Snapshot.SaveVersion != SnapshotVersion) { return Fail(TEXT("UnsupportedSaveVersion")); }
    if (!IsStableId(Snapshot.ContentRevision)) { return Fail(TEXT("InvalidContentRevision")); }
    if (!Snapshot.RunId.IsValid()) { return Fail(TEXT("InvalidRunId")); }
    if (!IsStableId(Snapshot.LevelId) || !IsStableId(Snapshot.NodeId)
        || !IsStableId(Snapshot.EncounterId) || !IsStableId(Snapshot.CheckpointId))
    { return Fail(TEXT("InvalidCheckpointIds")); }
    if (!ValidateIds(Snapshot.OrderedWaveIds, MaxWaveIds, true)) { return Fail(TEXT("InvalidOrderedWaveIds")); }
    // Num() represents a completed encounter entrance; playable entrances use 0..Num()-1.
    if (Snapshot.WaveOrBossPhaseIndex < 0 || Snapshot.WaveOrBossPhaseIndex > Snapshot.OrderedWaveIds.Num())
    { return Fail(TEXT("InvalidWaveOrBossPhaseIndex")); }
    if (Snapshot.EntryTransform.ContainsNaN()) { return Fail(TEXT("InvalidEntryTransform")); }
    const FVector Translation = Snapshot.EntryTransform.GetTranslation();
    const FVector Scale = Snapshot.EntryTransform.GetScale3D();
    const FQuat Rotation = Snapshot.EntryTransform.GetRotation();
    if (!IsFiniteRange(Translation.X, -1.0e9, 1.0e9) || !IsFiniteRange(Translation.Y, -1.0e9, 1.0e9)
        || !IsFiniteRange(Translation.Z, -1.0e9, 1.0e9)
        || !IsFiniteRange(Scale.X, 0.0001, 10000.0) || !IsFiniteRange(Scale.Y, 0.0001, 10000.0)
        || !IsFiniteRange(Scale.Z, 0.0001, 10000.0) || Rotation.ContainsNaN() || !Rotation.IsNormalized())
    { return Fail(TEXT("InvalidEntryTransform")); }
    if (!IsFiniteRange(Snapshot.EntryControlRotation.Pitch, -1.0e9, 1.0e9)
        || !IsFiniteRange(Snapshot.EntryControlRotation.Yaw, -1.0e9, 1.0e9)
        || !IsFiniteRange(Snapshot.EntryControlRotation.Roll, -1.0e9, 1.0e9))
    { return Fail(TEXT("InvalidEntryControlRotation")); }
    if (!FMath::IsFinite(Snapshot.PlayerResourcePreset.Health) || Snapshot.PlayerResourcePreset.Health <= 0.0f
        || Snapshot.PlayerResourcePreset.Health > 1000000.0f
        || !IsFiniteRange(Snapshot.PlayerResourcePreset.Guard, 0.0, 1000000.0))
    { return Fail(TEXT("InvalidPlayerResourcePreset")); }
    if (!IsFiniteRange(Snapshot.ProgressionState.LingQi, 0.0, 1000000.0)
        || !IsFiniteRange(Snapshot.ProgressionState.BurstEnergy, 0.0, 100.0)
        || Snapshot.ProgressionState.UpgradeLevel < 1 || Snapshot.ProgressionState.UpgradeLevel > 3)
    { return Fail(TEXT("InvalidProgressionState")); }
    if (!ValidateIds(Snapshot.ProgressionState.RewardedEventIds, MaxRewardIds))
    { return Fail(TEXT("InvalidRewardEventIds")); }
    if (!UNLRunStateSubsystem::ValidateMasterRewards(Snapshot.ProgressionState))
    { return Fail(TEXT("InvalidMasterRewardLedger")); }
    if (!IsStableId(Snapshot.ObjectiveState.StableId, true)
        || !IsFiniteRange(Snapshot.ObjectiveState.Integrity, 0.0, 1000000.0)
        || !IsFiniteRange(Snapshot.ObjectiveState.RescueProgress, 0.0, 1000000.0)
        || !ValidateIds(Snapshot.ObjectiveState.InterferenceSourceIds, MaxInterferenceIds))
    { return Fail(TEXT("InvalidObjectiveSnapshot")); }
    if (Snapshot.ObjectiveState.StableId.IsNone() && (Snapshot.ObjectiveState.Integrity != 0.0f
        || Snapshot.ObjectiveState.RescueProgress != 0.0f || Snapshot.ObjectiveState.bCompleted
        || !Snapshot.ObjectiveState.InterferenceSourceIds.IsEmpty()))
    { return Fail(TEXT("MissingObjectiveStableId")); }
    if (!ValidateIds(Snapshot.CompletedMilestones, MaxMilestoneIds))
    { return Fail(TEXT("InvalidCompletedMilestones")); }
    OutFailureReason = NAME_None;
    return true;
}

bool UNLCheckpointService::SetInMemoryCheckpoint(const FNLCheckpointSnapshot& Snapshot)
{
    if (!ValidateSnapshot(Snapshot, LastFailureReason))
    {
        LastPersistenceStatus = TEXT("Failed");
        return false;
    }
    CurrentSnapshot = Snapshot;
    bHasCheckpoint = true;
    LastPersistenceStatus = TEXT("InMemoryOnly");
    return true;
}

bool UNLCheckpointService::GetSnapshot(FNLCheckpointSnapshot& OutSnapshot) const
{
    if (!bHasCheckpoint) { return false; }
    OutSnapshot = CurrentSnapshot;
    return true;
}

bool UNLCheckpointService::LoadCheckpoint(FName ExpectedLevelId, FName ExpectedEncounterId,
    FName ExpectedContentRevision, const TArray<FName>& ExpectedOrderedWaveIds)
{
    using namespace NLCheckpoint;
    LastPersistenceStatus = TEXT("Failed");
    if (!IsStableId(ExpectedLevelId) || !IsStableId(ExpectedEncounterId)
        || !IsStableId(ExpectedContentRevision) || !ValidateIds(ExpectedOrderedWaveIds, MaxWaveIds, true))
    {
        LastFailureReason = TEXT("InvalidExpectedCheckpointContent");
        return false;
    }
    const FCheckpointPaths Paths(ExpectedLevelId, ExpectedEncounterId, ExpectedContentRevision, ExpectedOrderedWaveIds);
    FNLCheckpointSnapshot Candidate;
    TArray<uint8> Bytes;
    FName PrimaryFailure = NAME_None;
    if (ReadCheckpointFile(Paths.Primary, Candidate, Bytes, PrimaryFailure)
        && MatchesContent(Candidate, ExpectedLevelId, ExpectedEncounterId,
            ExpectedContentRevision, ExpectedOrderedWaveIds, PrimaryFailure))
    {
        CurrentSnapshot = Candidate;
        bHasCheckpoint = true;
        LastFailureReason = NAME_None;
        LastPersistenceStatus = TEXT("LoadedPrimary");
        return true;
    }
    FName BackupFailure = NAME_None;
    if (ReadCheckpointFile(Paths.Backup, Candidate, Bytes, BackupFailure)
        && MatchesContent(Candidate, ExpectedLevelId, ExpectedEncounterId,
            ExpectedContentRevision, ExpectedOrderedWaveIds, BackupFailure))
    {
        CurrentSnapshot = Candidate;
        bHasCheckpoint = true;
        LastFailureReason = PrimaryFailure;
        LastPersistenceStatus = TEXT("LoadedBackup");
        return true;
    }
    LastFailureReason = PrimaryFailure == FName(TEXT("CheckpointMissing")) ? BackupFailure : PrimaryFailure;
    return false;
}

bool UNLCheckpointService::WriteCheckpoint(const FNLCheckpointSnapshot& Snapshot)
{
    using namespace NLCheckpoint;
    LastPersistenceStatus = TEXT("Failed");
    if (!ValidateSnapshot(Snapshot, LastFailureReason)) { return false; }
#if !(PLATFORM_WINDOWS || PLATFORM_LINUX || PLATFORM_MAC || PLATFORM_ANDROID || PLATFORM_IOS)
    LastFailureReason = TEXT("AtomicReplaceUnsupportedPlatform");
    return false;
#endif
    TArray<uint8> NewBytes;
    if (!BuildEnvelope(Snapshot, NewBytes, LastFailureReason)) { return false; }
    const FCheckpointPaths Paths(Snapshot.LevelId, Snapshot.EncounterId, Snapshot.ContentRevision, Snapshot.OrderedWaveIds);
    IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
    FNLCheckpointSnapshot Existing;
    TArray<uint8> PrimaryBytes, BackupBytes;
    FName PrimaryFailure = NAME_None, BackupFailure = NAME_None;
    const bool bPrimaryValid = ReadCheckpointFile(Paths.Primary, Existing, PrimaryBytes, PrimaryFailure)
        && MatchesContent(Existing, Snapshot.LevelId, Snapshot.EncounterId,
            Snapshot.ContentRevision, Snapshot.OrderedWaveIds, PrimaryFailure);
    const bool bBackupValid = ReadCheckpointFile(Paths.Backup, Existing, BackupBytes, BackupFailure)
        && MatchesContent(Existing, Snapshot.LevelId, Snapshot.EncounterId,
            Snapshot.ContentRevision, Snapshot.OrderedWaveIds, BackupFailure);
    const bool bPrimaryMissing = PrimaryFailure == FName(TEXT("CheckpointMissing"));
    const bool bBackupMissing = BackupFailure == FName(TEXT("CheckpointMissing"));
    // Preserve damaged/unknown saves for diagnosis if there is no valid recovery copy.
    if (!bPrimaryValid && !bBackupValid && !(bPrimaryMissing && bBackupMissing))
    {
        LastFailureReason = bPrimaryMissing ? BackupFailure : PrimaryFailure;
        return false;
    }
    if (!Files.CreateDirectoryTree(*Paths.Directory))
    {
        LastFailureReason = TEXT("CheckpointDirectoryCreateFailed");
        return false;
    }
    if (!WriteFlushedTemp(Paths.PrimaryTemp, NewBytes))
    {
        LastFailureReason = TEXT("CheckpointTempWriteFailed");
        return false;
    }
    // Backup is replaced only with a validated primary, or the first valid checkpoint.
    // A corrupt primary is never promoted over an existing valid backup.
    if (bPrimaryValid || (!bBackupValid && bPrimaryMissing && bBackupMissing))
    {
        const TArray<uint8>& BackupSource = bPrimaryValid ? PrimaryBytes : NewBytes;
        if (!WriteFlushedTemp(Paths.BackupTemp, BackupSource) || !AtomicReplace(Paths.Backup, Paths.BackupTemp))
        {
            LastFailureReason = TEXT("CheckpointBackupCommitFailed");
            return false;
        }
    }
    if (!AtomicReplace(Paths.Primary, Paths.PrimaryTemp))
    {
        LastFailureReason = TEXT("CheckpointPrimaryCommitFailed");
        return false;
    }
    CurrentSnapshot = Snapshot;
    bHasCheckpoint = true;
    LastFailureReason = NAME_None;
    LastPersistenceStatus = TEXT("Saved");
    return true;
}
