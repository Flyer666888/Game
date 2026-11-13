#if WITH_DEV_AUTOMATION_TESTS

#include "Engine/GameInstance.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/Paths.h"
#include "Progression/NLRunStateSubsystem.h"
#include "Progression/NLUpgradeDefinition.h"
#include <limits>

#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#endif

namespace NLLingQiTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

    struct FRunFixture
    {
        UGameInstance* Instance = NewObject<UGameInstance>();
        UNLRunStateSubsystem* Run = NewObject<UNLRunStateSubsystem>(Instance);
        UNLUpgradeDefinition* Definition = NewObject<UNLUpgradeDefinition>(Instance);
        TArray<FGuid> OwnedRuns;

        FRunFixture()
        {
            StartNewRun();
            Run->ConfigureUpgradeDefinition(Definition);
        }
        void StartNewRun()
        {
            const FGuid Id = FGuid::NewGuid();
            OwnedRuns.Add(Id);
            Run->BeginRun(Id);
        }
        ~FRunFixture()
        {
            // Only GUIDs created by this fixture can have a file removed.
            IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
            for (FGuid Id : OwnedRuns)
            {
                const FString Path = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(),
                    TEXT("SaveGames/NilinMasterRewards"), Id.ToString(EGuidFormats::Digits) + TEXT(".nlmr")));
                Files.DeleteFile(*Path);
                Files.DeleteFile(*(Path + TEXT(".tmp")));
            }
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLingQiThresholdTest,
    "Nilin.Progression.LingQi.ThresholdAndUniqueRewards", NLLingQiTests::Flags)
bool FNLLingQiThresholdTest::RunTest(const FString& Parameters)
{
    using namespace NLLingQiTests;
    FRunFixture Fixture;
    UNLRunStateSubsystem* Run = Fixture.Run;
    TestEqual(TEXT("Configured ordinary defeat yields one LingQi"), Run->GetLingQiPerDefeat(), 1.0f);
    TestEqual(TEXT("First upgrade uses the GDD forty-point threshold"), Run->GetNextUpgradeThreshold(), 40.0f);
    for (int32 Index = 0; Index < 39; ++Index)
    {
        const FName Id(*FString::Printf(TEXT("Bcourt.Wave.01.Spawn.%04d"), Index));
        TestTrue(TEXT("Each actual stable defeat event awards once"), Run->AwardLingQi(Id, 1.0f));
    }
    TestEqual(TEXT("Thirty-nine points stay at level one"), Run->GetProgressionState().UpgradeLevel, 1);
    TestEqual(TEXT("Level one damage is unmodified"), Run->GetPlayerDamageMultiplier(), 1.0f);
    const FName Fortieth = TEXT("Bcourt.Wave.01.Spawn.0039");
    TestTrue(TEXT("Fortieth unique defeat crosses the threshold"), Run->AwardLingQi(Fortieth, 1.0f));
    TestEqual(TEXT("Exactly forty actual points were earned"), Run->GetProgressionState().LingQi, 40.0f);
    TestEqual(TEXT("Threshold produces level two"), Run->GetProgressionState().UpgradeLevel, 2);
    TestEqual(TEXT("One authoritative configured multiplier is exposed"), Run->GetPlayerDamageMultiplier(), 1.25f);
    TestEqual(TEXT("No third upgrade is promised by this first-level slice"), Run->GetNextUpgradeThreshold(), 0.0f);
    TestFalse(TEXT("A repeated death callback cannot grant a second reward"), Run->AwardLingQi(Fortieth, 999.0f));
    TestTrue(TEXT("Duplicates are a clean no-op rather than a failure"), Run->GetLastFailureReason().IsNone());
    TestEqual(TEXT("Duplicate callback leaves currency untouched"), Run->GetProgressionState().LingQi, 40.0f);
    TestEqual(TEXT("Duplicate callback leaves ledger size untouched"), Run->GetDefeatEventCount(), 40);
    TestTrue(TEXT("Later unique deaths continue accumulating ordinary currency"), Run->AwardLingQi(TEXT("Later.Spawn.0001"), 100.0f));
    TestEqual(TEXT("Exceeding the future threshold does not enable unfinished level three"), Run->GetProgressionState().UpgradeLevel, 2);
    TestEqual(TEXT("Later defeats do not compound damage multipliers"), Run->GetPlayerDamageMultiplier(), 1.25f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLingQiAtomicValidationTest,
    "Nilin.Progression.LingQi.InvalidRewardsAreAtomic", NLLingQiTests::Flags)
bool FNLLingQiAtomicValidationTest::RunTest(const FString& Parameters)
{
    using namespace NLLingQiTests;
    FRunFixture Fixture;
    UNLRunStateSubsystem* Run = Fixture.Run;
    const FName Retryable = TEXT("Test.InvalidThenValid");
    for (float Invalid : {0.0f, -1.0f, std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity()})
        TestFalse(TEXT("Non-positive or non-finite amounts are rejected"), Run->AwardLingQi(Retryable, Invalid));
    TestFalse(TEXT("Missing identity cannot grant currency"), Run->AwardLingQi(NAME_None, 1.0f));
    FString LongName;
    for (int32 Index = 0; Index < 129; ++Index) LongName += TEXT("x");
    const FName LongId(*LongName);
    TestFalse(TEXT("Unbounded identity cannot grant currency"), Run->AwardLingQi(LongId, 1.0f));
    TestEqual(TEXT("Rejected events never consume ledger entries"), Run->GetDefeatEventCount(), 0);
    TestEqual(TEXT("Rejected events never grant partial currency"), Run->GetProgressionState().LingQi, 0.0f);
    TestTrue(TEXT("The same identity remains usable after its invalid callback"), Run->AwardLingQi(Retryable, 1.0f));
    TestEqual(TEXT("Exactly one valid point is committed"), Run->GetProgressionState().LingQi, 1.0f);

    FNLProgressionState NearLimit;
    NearLimit.LingQi = 999999.0f;
    NearLimit.UpgradeLevel = 2;
    TestTrue(TEXT("A valid bounded entrance can be restored"), Run->RestoreProgressionState(NearLimit));
    TestFalse(TEXT("Overflow above the save-schema currency cap is rejected"), Run->AwardLingQi(TEXT("Test.Limit"), 2.0f));
    TestFalse(TEXT("An amount lost to float precision is not recorded as earned currency"), Run->AwardLingQi(TEXT("Test.Precision"), .00001f));
    TestEqual(TEXT("Cap and precision rejection both preserve the ledger"), Run->GetDefeatEventCount(), 0);
    TestEqual(TEXT("Cap and precision rejection both preserve currency"), Run->GetProgressionState().LingQi, 999999.0f);
    TestTrue(TEXT("A valid capped value still commits with the formerly rejected ID"), Run->AwardLingQi(TEXT("Test.Limit"), 1.0f));
    TestEqual(TEXT("The maximum legal currency remains representable"), Run->GetProgressionState().LingQi, 1000000.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLingQiFloorTest,
    "Nilin.Progression.LingQi.LevelEndFloorDoesNotMintCurrency", NLLingQiTests::Flags)
bool FNLLingQiFloorTest::RunTest(const FString& Parameters)
{
    using namespace NLLingQiTests;
    FRunFixture Fixture;
    UNLRunStateSubsystem* Run = Fixture.Run;
    TestTrue(TEXT("One point can be earned before the level-end fallback"), Run->AwardLingQi(TEXT("Test.Defeat"), 1.0f));
    TestTrue(TEXT("The first-level boundary guarantees level two"), Run->EnsureUpgradeLevel(2));
    const FNLProgressionState AfterFloor = Run->GetProgressionState();
    TestEqual(TEXT("The floor does not pretend forty points were earned"), AfterFloor.LingQi, 1.0f);
    TestEqual(TEXT("The floor does not synthesize enemy defeats"), AfterFloor.RewardedEventIds.Num(), 1);
    TestEqual(TEXT("The floor grants the real level-two effect"), Run->GetPlayerDamageMultiplier(), 1.25f);
    for (int32 Index = 0; Index < 10; ++Index)
        TestTrue(TEXT("Repeated completion callbacks leave an already met floor satisfied"), Run->EnsureUpgradeLevel(2));
    TestEqual(TEXT("Repeated floor callbacks never accumulate currency"), Run->GetProgressionState().LingQi, AfterFloor.LingQi);
    TestEqual(TEXT("Repeated floor callbacks never compound the damage effect"), Run->GetPlayerDamageMultiplier(), 1.25f);
    TestFalse(TEXT("A first-level floor cannot invent the unimplemented third upgrade"), Run->EnsureUpgradeLevel(3));
    TestFalse(TEXT("Invalid zero-level request is rejected"), Run->EnsureUpgradeLevel(0));
    TestTrue(TEXT("A lesser valid floor never downgrades the player"), Run->EnsureUpgradeLevel(1));
    TestEqual(TEXT("Level two remains earned"), Run->GetProgressionState().UpgradeLevel, 2);

    FNLProgressionState Legacy;
    Legacy.LingQi = 100.0f;
    Legacy.UpgradeLevel = 3;
    TestTrue(TEXT("Existing schema-valid level-three saves remain loadable"), Run->RestoreProgressionState(Legacy));
    TestTrue(TEXT("A level-two floor accepts an already higher saved level"), Run->EnsureUpgradeLevel(2));
    TestEqual(TEXT("The first-level rule never downgrades the saved level"), Run->GetProgressionState().UpgradeLevel, 3);
    TestEqual(TEXT("Only the implemented level-two multiplier is applied"), Run->GetPlayerDamageMultiplier(), 1.25f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLingQiRetryRollbackTest,
    "Nilin.Progression.LingQi.TenRetriesRollbackCurrencyLevelAndEventIds", NLLingQiTests::Flags)
bool FNLLingQiRetryRollbackTest::RunTest(const FString& Parameters)
{
    using namespace NLLingQiTests;
    FRunFixture Fixture;
    UNLRunStateSubsystem* Run = Fixture.Run;
    TestTrue(TEXT("Completed earlier segment earns its currency"), Run->AwardLingQi(TEXT("Earlier.Complete"), 39.0f));
    TestTrue(TEXT("Entrance has a measured burst resource"), Run->SetBurstEnergy(27.0f));
    const FNLProgressionState Entrance = Run->GetProgressionState();
    for (int32 Retry = 0; Retry < 10; ++Retry)
    {
        TestTrue(TEXT("An uncommitted segment defeat can cross the upgrade threshold"), Run->AwardLingQi(TEXT("Current.Wave.01.Spawn.0001"), 1.0f));
        Run->SetBurstEnergy(80.0f);
        TestEqual(TEXT("The attempt really gained an upgrade before failing"), Run->GetProgressionState().UpgradeLevel, 2);
        TestTrue(TEXT("Retry restores the immutable segment entrance"), Run->RestoreProgressionState(Entrance));
        TestEqual(TEXT("Repeated retries cannot farm partial-attempt LingQi"), Run->GetProgressionState().LingQi, 39.0f);
        TestEqual(TEXT("A failed attempt's upgrade rolls back"), Run->GetProgressionState().UpgradeLevel, 1);
        TestEqual(TEXT("Damage effect rolls back with the saved level"), Run->GetPlayerDamageMultiplier(), 1.0f);
        TestEqual(TEXT("Burst resource rolls back alongside growth"), Run->GetProgressionState().BurstEnergy, 27.0f);
        TestEqual(TEXT("Only the earlier completed segment's event remains"), Run->GetDefeatEventCount(), 1);
        TestEqual(TEXT("Retry does not replay reward feedback"), Run->GetLastLingQiAwardAmount(), 0.0f);
        TestEqual(TEXT("Retry clears upgrade feedback timing"), Run->GetLastUpgradeTimeSeconds(), -1.0);
    }
    TestTrue(TEXT("Finally completing that same stable enemy rewards it once"), Run->AwardLingQi(TEXT("Current.Wave.01.Spawn.0001"), 1.0f));
    TestEqual(TEXT("Successful completion has forty points, not fifty"), Run->GetProgressionState().LingQi, 40.0f);
    TestEqual(TEXT("Successful completion retains the actual upgrade"), Run->GetProgressionState().UpgradeLevel, 2);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLingQiQuestPreservationTest,
    "Nilin.Progression.LingQi.RollbackKeepsQuestClaimsAndNewRunResetsGrowth", NLLingQiTests::Flags)
bool FNLLingQiQuestPreservationTest::RunTest(const FString& Parameters)
{
    using namespace NLLingQiTests;
    FRunFixture Fixture;
    UNLRunStateSubsystem* Run = Fixture.Run;
    const FNLProgressionState Entrance = Run->GetProgressionState();
    TestTrue(TEXT("The attempt durably earns one master seal"), Run->GrantMasterSeal(TEXT("GM01"), TEXT("SwordSeal"), FVector(1, 2, 3)));
    TestTrue(TEXT("The separate first-defeat healing supply is claimed"), Run->CollectMasterReward(TEXT("GM01")));
    TestTrue(TEXT("The same attempt earns ordinary LingQi"), Run->AwardLingQi(TEXT("Attempt.Master"), 40.0f));
    TestTrue(TEXT("Retry restores ordinary growth"), Run->RestoreProgressionState(Entrance));
    TestEqual(TEXT("Failed-attempt currency rolls back"), Run->GetProgressionState().LingQi, 0.0f);
    TestEqual(TEXT("Failed-attempt upgrade rolls back"), Run->GetProgressionState().UpgradeLevel, 1);
    TestTrue(TEXT("A durable master seal is not lost through a growth rollback"), Run->HasSeal(TEXT("SwordSeal")));
    TestTrue(TEXT("A consumed health reward is not duplicated by retry"), Run->HasCollectedMasterReward(TEXT("GM01")));
    TestEqual(TEXT("Original master reward location survives rollback"), Run->GetProgressionState().MasterRewardLocations.FindRef(TEXT("GM01")), FVector(1, 2, 3));

    TestTrue(TEXT("Growth can be earned again in a successful attempt"), Run->AwardLingQi(TEXT("Attempt.Master"), 40.0f));
    const FGuid ExistingRun = Run->GetRunId();
    Run->BeginRun(ExistingRun);
    TestEqual(TEXT("Re-entering the same run does not erase growth"), Run->GetProgressionState().LingQi, 40.0f);
    Fixture.StartNewRun();
    TestEqual(TEXT("An explicit new run starts with zero LingQi"), Run->GetProgressionState().LingQi, 0.0f);
    TestEqual(TEXT("An explicit new run starts at level one"), Run->GetProgressionState().UpgradeLevel, 1);
    TestEqual(TEXT("An explicit new run starts with an empty reward ledger"), Run->GetDefeatEventCount(), 0);
    TestFalse(TEXT("An explicit new run does not inherit quest seals"), Run->HasSeal(TEXT("SwordSeal")));
    TestEqual(TEXT("The current level's configured tuning remains available for the new run"), Run->GetLingQiPerDefeat(), 1.0f);
    TestEqual(TEXT("New-run reset clears award feedback"), Run->GetLastLingQiAwardAmount(), 0.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLingQiConfigurationTest,
    "Nilin.Progression.LingQi.OptInDefinitionValidationAndFrozenEffects", NLLingQiTests::Flags)
bool FNLLingQiConfigurationTest::RunTest(const FString& Parameters)
{
    using namespace NLLingQiTests;
    FRunFixture Fixture;
    UNLRunStateSubsystem* Run = Fixture.Run;
    TestTrue(TEXT("Default definition is valid"), Fixture.Definition->IsValidDefinition());
    TestTrue(TEXT("Configured rules permit first-level growth"), Run->AwardLingQi(TEXT("Test.LevelUp"), 40.0f));
    Fixture.Definition->LevelTwoDamageMultiplier = 9.0f;
    Fixture.Definition->FirstUpgradeThreshold = 100.0f;
    Fixture.Definition->LingQiPerDefeat = 50.0f;
    TestEqual(TEXT("PIE edits do not silently alter the active damage multiplier"), Run->GetPlayerDamageMultiplier(), 1.25f);
    TestEqual(TEXT("PIE edits do not silently alter the active defeat reward"), Run->GetLingQiPerDefeat(), 1.0f);
    UNLUpgradeDefinition* Invalid = NewObject<UNLUpgradeDefinition>(Fixture.Instance);
    Invalid->LevelTwoDamageMultiplier = std::numeric_limits<float>::quiet_NaN();
    TestFalse(TEXT("Invalid definitions cannot replace an active configuration"), Run->ConfigureUpgradeDefinition(Invalid));
    TestEqual(TEXT("Failed configuration keeps the previous effect"), Run->GetPlayerDamageMultiplier(), 1.25f);
    TestTrue(TEXT("Failed configuration keeps the original asset ownership"), Run->GetUpgradeDefinition() == Fixture.Definition);
    TestTrue(TEXT("A scene can explicitly remove its growth configuration"), Run->ConfigureUpgradeDefinition(nullptr));
    TestEqual(TEXT("A scene without a definition applies no damage bonus"), Run->GetPlayerDamageMultiplier(), 1.0f);
    TestEqual(TEXT("Removing the configuration does not delete saved currency"), Run->GetProgressionState().LingQi, 40.0f);
    TestEqual(TEXT("Removing the configuration does not delete a saved upgrade"), Run->GetProgressionState().UpgradeLevel, 2);
    TestFalse(TEXT("An unconfigured scene cannot grant currency"), Run->AwardLingQi(TEXT("Disabled.Event"), 1.0f));
    TestFalse(TEXT("An unconfigured scene cannot apply a level-end guarantee"), Run->EnsureUpgradeLevel(2));
    TestEqual(TEXT("No next upgrade is advertised without a definition"), Run->GetNextUpgradeThreshold(), 0.0f);
    TestTrue(TEXT("The legacy ledger-only API remains valid"), Run->RecordEnemyDefeat(TEXT("Legacy.Lab.Event")));
    TestEqual(TEXT("Legacy labs still do not grant currency"), Run->GetProgressionState().LingQi, 40.0f);
    return true;
}

#if PLATFORM_WINDOWS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLingQiReadLockedLedgerRetryTest,
    "Nilin.Progression.LingQi.UnchangedFourSealLedgerDoesNotNeedRetryWrites", NLLingQiTests::Flags)
bool FNLLingQiReadLockedLedgerRetryTest::RunTest(const FString& Parameters)
{
    using namespace NLLingQiTests;
    FRunFixture Fixture;
    UNLRunStateSubsystem* Run = Fixture.Run;
    const FName Masters[] = {TEXT("GM01"), TEXT("GM02"), TEXT("GM03"), TEXT("GM04")};
    for (int32 Index = 0; Index < 4; ++Index)
        if (!TestTrue(TEXT("Fixture durably earns each of the four seals"),
            Run->GrantMasterSeal(Masters[Index], UNLRunStateSubsystem::SealForMaster(Masters[Index]), FVector(Index, 2, 3)))) return false;
    if (!TestTrue(TEXT("Fixture durably claims its first health supply"), Run->CollectMasterReward(TEXT("GM01")))) return false;
    const FNLProgressionState Entrance = Run->GetProgressionState();
    const FString Path = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(),
        TEXT("SaveGames/NilinMasterRewards"), Run->GetRunId().ToString(EGuidFormats::Digits) + TEXT(".nlmr")));
    const FString TemporaryPath = Path + TEXT(".tmp");
    FString NativePath = Path;
    FPaths::MakePlatformFilename(NativePath);
    IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
    FNLProgressionState AddedClaim = Entrance;
    AddedClaim.CollectedMasterRewards.Add(TEXT("GM02"));
    {
        // Use a native handle because the editor's optional share-delete CVar can
        // override IPlatformFile::OpenRead. This handle always denies replacement.
        struct FReadLock
        {
            HANDLE Handle = INVALID_HANDLE_VALUE;
            ~FReadLock() { if (Handle != INVALID_HANDLE_VALUE) ::CloseHandle(Handle); }
        } Lock;
        Lock.Handle = ::CreateFileW(*NativePath, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (!TestTrue(TEXT("An exact fixture-owned ledger is locked against replacement"), Lock.Handle != INVALID_HANDLE_VALUE)) return false;
        TestFalse(TEXT("The lock demonstrably blocks a new durable claim"), Run->CollectMasterReward(TEXT("GM02")));
        TestEqual(TEXT("The blocked mutation reports the actual commit failure"), Run->GetLastFailureReason(), FName(TEXT("MasterRewardLedgerCommitFailed")));
        TestFalse(TEXT("Failed durable claim did not mutate current ownership"), Run->HasCollectedMasterReward(TEXT("GM02")));
        Files.DeleteFile(*TemporaryPath);
        if (!TestFalse(TEXT("The failed probe's temporary file is removed before checking retry writes"), Files.FileExists(*TemporaryPath))) return false;

        for (int32 Attempt = 0; Attempt < 10; ++Attempt)
        {
            TestTrue(TEXT("A failed attempt earns ordinary currency in memory"), Run->AwardLingQi(TEXT("FailedSegment.Spawn.01"), 40.0f));
            TestTrue(TEXT("Growth rollback succeeds while the unchanged master ledger cannot be replaced"), Run->RestoreProgressionState(Entrance));
            TestEqual(TEXT("Rollback restores ordinary currency"), Run->GetProgressionState().LingQi, 0.0f);
            TestEqual(TEXT("Rollback restores the original upgrade level"), Run->GetProgressionState().UpgradeLevel, 1);
            TestEqual(TEXT("All four seals remain owned"), Run->GetCollectedSealIds().Num(), 4);
            TestTrue(TEXT("The existing health-supply claim remains consumed"), Run->HasCollectedMasterReward(TEXT("GM01")));
            TestFalse(TEXT("No temporary ledger write is attempted for unchanged claims"), Files.FileExists(*TemporaryPath));
        }
        TestFalse(TEXT("A restored snapshot adding a claim still requires a durable write"), Run->RestoreProgressionState(AddedClaim));
        TestFalse(TEXT("A blocked new snapshot claim is not partially committed"), Run->HasCollectedMasterReward(TEXT("GM02")));
    }
    TestTrue(TEXT("After releasing the lock, a genuinely new snapshot claim can commit"), Run->RestoreProgressionState(AddedClaim));
    UNLRunStateSubsystem* Reloaded = NewObject<UNLRunStateSubsystem>(Fixture.Instance);
    Reloaded->BeginRun(Run->GetRunId());
    TestTrue(TEXT("The new claim survives a fresh subsystem reload"), Reloaded->HasCollectedMasterReward(TEXT("GM02")));
    TestEqual(TEXT("All four quest seals survive that reload"), Reloaded->GetCollectedSealIds().Num(), 4);
    return true;
}
#endif

#endif
