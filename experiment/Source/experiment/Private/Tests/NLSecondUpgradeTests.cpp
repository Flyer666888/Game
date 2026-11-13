#if WITH_DEV_AUTOMATION_TESTS

#include "Engine/GameInstance.h"
#include "Misc/AutomationTest.h"
#include "Progression/NLRunStateSubsystem.h"
#include "Progression/NLUpgradeDefinition.h"
#include "Tests/NLRunCallbackTestListener.h"
#include <limits>

namespace NLSecondUpgradeTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

    struct FRunFixture
    {
        UGameInstance* Instance = NewObject<UGameInstance>();
        UNLRunStateSubsystem* Run = NewObject<UNLRunStateSubsystem>(Instance);
        UNLUpgradeDefinition* Definition = NewObject<UNLUpgradeDefinition>(Instance);
        UNLRunCallbackTestListener* Listener = NewObject<UNLRunCallbackTestListener>(Instance);

        explicit FRunFixture(bool bEnableSecond = true)
        {
            Definition->bEnableSecondUpgrade = bEnableSecond;
            Run->BeginRun(FGuid::NewGuid());
            Run->ConfigureUpgradeDefinition(Definition);
        }
        ~FRunFixture()
        {
            Run->OnRunStateChanged.RemoveDynamic(Listener, &UNLRunCallbackTestListener::HandleRunChanged);
        }
        void Observe(TFunction<void()> Callback)
        {
            Listener->Callback = MoveTemp(Callback);
            Run->OnRunStateChanged.AddUniqueDynamic(Listener, &UNLRunCallbackTestListener::HandleRunChanged);
        }
        void StopObserving()
        {
            Run->OnRunStateChanged.RemoveDynamic(Listener, &UNLRunCallbackTestListener::HandleRunChanged);
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLSecondUpgradeNaturalThresholdTest,
    "Nilin.Progression.SecondUpgrade.CumulativeThresholdsAndUniqueRewards", NLSecondUpgradeTests::Flags)
bool FNLSecondUpgradeNaturalThresholdTest::RunTest(const FString& Parameters)
{
    using namespace NLSecondUpgradeTests;
    FRunFixture F;
    TestEqual(TEXT("Level one still advertises forty total LingQi"), F.Run->GetNextUpgradeThreshold(), 40.0f);
    for (int32 Index = 1; Index <= 100; ++Index)
    {
        const FName Event(*FString::Printf(TEXT("SecondUpgrade.Spawn.%03d"), Index));
        if (!TestTrue(TEXT("Each unique defeat commits one real point"), F.Run->AwardLingQi(Event, 1.0f))) return false;
        if (Index == 39) TestEqual(TEXT("Thirty-nine remains level one"), F.Run->GetProgressionState().UpgradeLevel, 1);
        if (Index == 40)
        {
            TestEqual(TEXT("The first threshold remains level two"), F.Run->GetProgressionState().UpgradeLevel, 2);
            TestEqual(TEXT("The first effect remains unchanged"), F.Run->GetPlayerDamageMultiplier(), 1.25f);
            TestEqual(TEXT("The second threshold is cumulative one hundred"), F.Run->GetNextUpgradeThreshold(), 100.0f);
        }
        if (Index == 99) TestEqual(TEXT("Ninety-nine remains level two"), F.Run->GetProgressionState().UpgradeLevel, 2);
    }
    TestEqual(TEXT("The hundredth defeat reaches level three"), F.Run->GetProgressionState().UpgradeLevel, 3);
    TestEqual(TEXT("Upgrading never spends earned currency"), F.Run->GetProgressionState().LingQi, 100.0f);
    TestEqual(TEXT("Level three replaces, rather than multiplies, the earlier effect"), F.Run->GetPlayerDamageMultiplier(), 1.5f);
    TestEqual(TEXT("No fourth upgrade is advertised"), F.Run->GetNextUpgradeThreshold(), 0.0f);
    TestFalse(TEXT("Duplicate final defeat cannot award again"), F.Run->AwardLingQi(TEXT("SecondUpgrade.Spawn.100"), 100.0f));
    TestEqual(TEXT("Duplicate keeps the currency and event ledger unchanged"), F.Run->GetDefeatEventCount(), 100);
    TestEqual(TEXT("Duplicate keeps exactly one hundred earned points"), F.Run->GetProgressionState().LingQi, 100.0f);
    TestTrue(TEXT("Later genuine defeats still earn currency"), F.Run->AwardLingQi(TEXT("SecondUpgrade.Later"), 10.0f));
    TestEqual(TEXT("Later rewards cannot compound the level-three multiplier"), F.Run->GetPlayerDamageMultiplier(), 1.5f);

    FRunFixture LargeReward;
    TestTrue(TEXT("A single legitimate reward can cross both thresholds atomically"), LargeReward.Run->AwardLingQi(TEXT("SecondUpgrade.LargeReward"), 100.0f));
    TestEqual(TEXT("A large award directly reaches the matching final level"), LargeReward.Run->GetProgressionState().UpgradeLevel, 3);
    TestEqual(TEXT("A large award still records only its one actual event"), LargeReward.Run->GetDefeatEventCount(), 1);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLSecondUpgradeLegacyOptInTest,
    "Nilin.Progression.SecondUpgrade.LegacyAssetsRemainOptIn", NLSecondUpgradeTests::Flags)
bool FNLSecondUpgradeLegacyOptInTest::RunTest(const FString& Parameters)
{
    using namespace NLSecondUpgradeTests;
    FRunFixture F(false);
    TestFalse(TEXT("Existing assets default to the first-level rules"), F.Definition->bEnableSecondUpgrade);
    TestTrue(TEXT("Legacy scene may legitimately accumulate one hundred points"), F.Run->AwardLingQi(TEXT("Legacy.Hundred"), 100.0f));
    TestEqual(TEXT("Legacy definition cannot naturally enable level three"), F.Run->GetProgressionState().UpgradeLevel, 2);
    TestEqual(TEXT("Legacy scene exposes its existing effect"), F.Run->GetPlayerDamageMultiplier(), 1.25f);
    TestEqual(TEXT("Legacy scene does not promise a disabled threshold"), F.Run->GetNextUpgradeThreshold(), 0.0f);
    TestFalse(TEXT("Legacy level boundary cannot force an unconfigured upgrade"), F.Run->EnsureUpgradeLevel(3));
    F.Definition->bEnableSecondUpgrade = true;
    TestTrue(TEXT("An explicitly enabled definition configures the second level"), F.Run->ConfigureUpgradeDefinition(F.Definition));
    TestEqual(TEXT("Configuration alone does not rewrite checkpoint-owned growth"), F.Run->GetProgressionState().UpgradeLevel, 2);
    TestTrue(TEXT("The next real reward evaluates the newly configured cumulative threshold"), F.Run->AwardLingQi(TEXT("OptIn.Next"), 1.0f));
    TestEqual(TEXT("Enabled progression can now reach level three"), F.Run->GetProgressionState().UpgradeLevel, 3);
    F.Definition->bEnableSecondUpgrade = false;
    TestTrue(TEXT("Returning to a legacy definition is supported"), F.Run->ConfigureUpgradeDefinition(F.Definition));
    TestEqual(TEXT("Changing definitions does not downgrade saved growth"), F.Run->GetProgressionState().UpgradeLevel, 3);
    TestEqual(TEXT("Legacy scenes still apply only their configured level-two effect"), F.Run->GetPlayerDamageMultiplier(), 1.25f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLSecondUpgradeFloorTest,
    "Nilin.Progression.SecondUpgrade.LevelEndFloorDoesNotMintCurrencyOrReplay", NLSecondUpgradeTests::Flags)
bool FNLSecondUpgradeFloorTest::RunTest(const FString& Parameters)
{
    using namespace NLSecondUpgradeTests;
    FRunFixture F;
    TestTrue(TEXT("An actual early defeat earns one point"), F.Run->AwardLingQi(TEXT("Floor.Earned"), 1.0f));
    TestTrue(TEXT("First level can still guarantee level two"), F.Run->EnsureUpgradeLevel(2));
    TestEqual(TEXT("The next target remains the cumulative hundred-point threshold"), F.Run->GetNextUpgradeThreshold(), 100.0f);
    int32 Notifications = 0;
    F.Observe([&Notifications]() { ++Notifications; });
    TestTrue(TEXT("Second level's authored floor guarantees level three"), F.Run->EnsureUpgradeLevel(3));
    for (int32 Repeat = 0; Repeat < 10; ++Repeat)
        TestTrue(TEXT("Repeated valid completion is an idempotent success"), F.Run->EnsureUpgradeLevel(3));
    TestEqual(TEXT("The floor broadcasts only the one real level change"), Notifications, 1);
    TestEqual(TEXT("The floor does not create unearned currency"), F.Run->GetProgressionState().LingQi, 1.0f);
    TestEqual(TEXT("The floor does not fabricate defeated enemies"), F.Run->GetDefeatEventCount(), 1);
    TestEqual(TEXT("The floor exposes the genuine level-three damage effect"), F.Run->GetPlayerDamageMultiplier(), 1.5f);
    TestEqual(TEXT("The floor does not replace the last actual LingQi reward"), F.Run->GetLastLingQiAwardAmount(), 1.0f);
    TestTrue(TEXT("A lesser valid floor does not downgrade earned progress"), F.Run->EnsureUpgradeLevel(2));
    TestFalse(TEXT("An unsupported fourth level is rejected"), F.Run->EnsureUpgradeLevel(4));
    TestFalse(TEXT("A zero level is rejected"), F.Run->EnsureUpgradeLevel(0));
    TestEqual(TEXT("Invalid requests and lower floors broadcast no extra upgrade"), Notifications, 1);
    F.StopObserving();
    TestTrue(TEXT("A scene can disable its growth effects"), F.Run->ConfigureUpgradeDefinition(nullptr));
    TestEqual(TEXT("No effect remains without an active definition"), F.Run->GetPlayerDamageMultiplier(), 1.0f);
    TestEqual(TEXT("The stored level is preserved when effects are disabled"), F.Run->GetProgressionState().UpgradeLevel, 3);
    TestFalse(TEXT("An unconfigured scene cannot guarantee an upgrade"), F.Run->EnsureUpgradeLevel(3));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLSecondUpgradeValidationTest,
    "Nilin.Progression.SecondUpgrade.InvalidTuningCannotReplaceConfiguration", NLSecondUpgradeTests::Flags)
bool FNLSecondUpgradeValidationTest::RunTest(const FString& Parameters)
{
    using namespace NLSecondUpgradeTests;
    FRunFixture F;
    F.Run->AwardLingQi(TEXT("Valid.Entrance"), 99.0f);
    for (float Threshold : {0.0f, 39.0f, 40.0f, 1000001.0f, std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity()})
    {
        UNLUpgradeDefinition* Invalid = NewObject<UNLUpgradeDefinition>(F.Instance);
        Invalid->bEnableSecondUpgrade = true;
        Invalid->SecondUpgradeThreshold = Threshold;
        TestFalse(TEXT("Invalid or non-increasing second thresholds are rejected"), F.Run->ConfigureUpgradeDefinition(Invalid));
        TestTrue(TEXT("Rejected configuration preserves ownership of the previous asset"), F.Run->GetUpgradeDefinition() == F.Definition);
        TestEqual(TEXT("Rejected configuration preserves the cached next threshold"), F.Run->GetNextUpgradeThreshold(), 100.0f);
    }
    for (float Multiplier : {0.0f, 1.0f, 1.24f, 10.01f, std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity()})
    {
        UNLUpgradeDefinition* Invalid = NewObject<UNLUpgradeDefinition>(F.Instance);
        Invalid->bEnableSecondUpgrade = true;
        Invalid->LevelThreeDamageMultiplier = Multiplier;
        TestFalse(TEXT("Second upgrade cannot be non-finite, weaker, or above the supported cap"), F.Run->ConfigureUpgradeDefinition(Invalid));
        TestEqual(TEXT("Rejected tuning never changes the current effect"), F.Run->GetPlayerDamageMultiplier(), 1.25f);
    }
    TestFalse(TEXT("Invalid reward cannot consume the threshold-crossing event"), F.Run->AwardLingQi(TEXT("Valid.Final"), std::numeric_limits<float>::infinity()));
    TestEqual(TEXT("Invalid rewards keep the level and currency below the threshold"), F.Run->GetProgressionState().LingQi, 99.0f);
    TestTrue(TEXT("A valid reward with the rejected event ID can still commit"), F.Run->AwardLingQi(TEXT("Valid.Final"), 1.0f));
    TestEqual(TEXT("The last valid cached definition supplies the final effect"), F.Run->GetPlayerDamageMultiplier(), 1.5f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLSecondUpgradeCachedTuningTest,
    "Nilin.Progression.SecondUpgrade.RuntimeUsesValidatedCachedTuning", NLSecondUpgradeTests::Flags)
bool FNLSecondUpgradeCachedTuningTest::RunTest(const FString& Parameters)
{
    using namespace NLSecondUpgradeTests;
    FRunFixture F;
    F.Definition->bEnableSecondUpgrade = false;
    F.Definition->SecondUpgradeThreshold = 200.0f;
    F.Definition->LevelThreeDamageMultiplier = 9.0f;
    F.Definition->FirstUpgradeThreshold = 90.0f;
    F.Definition->LevelTwoDamageMultiplier = 8.0f;
    F.Definition->LingQiPerDefeat = 50.0f;
    TestEqual(TEXT("Live asset mutation cannot silently alter the first threshold"), F.Run->GetNextUpgradeThreshold(), 40.0f);
    TestEqual(TEXT("Live asset mutation cannot silently alter reward amounts"), F.Run->GetLingQiPerDefeat(), 1.0f);
    F.Run->AwardLingQi(TEXT("Cached.First"), 40.0f);
    TestEqual(TEXT("Cached first effect remains in use"), F.Run->GetPlayerDamageMultiplier(), 1.25f);
    TestEqual(TEXT("Cached enable flag and second threshold remain in use"), F.Run->GetNextUpgradeThreshold(), 100.0f);
    F.Run->AwardLingQi(TEXT("Cached.Second"), 60.0f);
    TestEqual(TEXT("Cached second effect remains in use"), F.Run->GetPlayerDamageMultiplier(), 1.5f);
    TestTrue(TEXT("An explicit valid configure applies replacement tuning"), F.Run->ConfigureUpgradeDefinition(F.Definition));
    TestEqual(TEXT("An explicit legacy configuration disables only the second effect"), F.Run->GetPlayerDamageMultiplier(), 8.0f);
    TestEqual(TEXT("Explicit configuration still preserves the stored level"), F.Run->GetProgressionState().UpgradeLevel, 3);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLSecondUpgradeRetryTest,
    "Nilin.Progression.SecondUpgrade.FailedAttemptRollsBackLevelCurrencyAndEventIds", NLSecondUpgradeTests::Flags)
bool FNLSecondUpgradeRetryTest::RunTest(const FString& Parameters)
{
    using namespace NLSecondUpgradeTests;
    FRunFixture F;
    F.Run->AwardLingQi(TEXT("Completed.EarlierPhases"), 99.0f);
    F.Run->SetBurstEnergy(27.0f);
    const FNLProgressionState Entry = F.Run->GetProgressionState();
    for (int32 Attempt = 0; Attempt < 10; ++Attempt)
    {
        TestTrue(TEXT("Retry may defeat the same stable enemy again"), F.Run->AwardLingQi(TEXT("Uncommitted.CurrentPhase"), 1.0f));
        TestEqual(TEXT("The failed attempt actually reached level three"), F.Run->GetProgressionState().UpgradeLevel, 3);
        F.Run->SetBurstEnergy(80.0f);
        TestTrue(TEXT("Retry restores the real entrance snapshot"), F.Run->RestoreProgressionState(Entry));
        TestEqual(TEXT("Failed segment currency is removed"), F.Run->GetProgressionState().LingQi, 99.0f);
        TestEqual(TEXT("Failed segment upgrade is removed"), F.Run->GetProgressionState().UpgradeLevel, 2);
        TestEqual(TEXT("Damage reads the restored level immediately"), F.Run->GetPlayerDamageMultiplier(), 1.25f);
        TestEqual(TEXT("Only completed earlier rewards remain recorded"), F.Run->GetDefeatEventCount(), 1);
        TestEqual(TEXT("Burst energy rolls back with the same snapshot"), F.Run->GetProgressionState().BurstEnergy, 27.0f);
        TestEqual(TEXT("Restore does not replay upgrade feedback"), F.Run->GetLastUpgradeTimeSeconds(), -1.0);
        TestEqual(TEXT("Restore clears the failed reward feedback"), F.Run->GetLastLingQiAwardAmount(), 0.0f);
    }
    TestTrue(TEXT("The eventually completed attempt may commit its actual reward"), F.Run->AwardLingQi(TEXT("Uncommitted.CurrentPhase"), 1.0f));
    const FNLProgressionState Completed = F.Run->GetProgressionState();
    TestTrue(TEXT("A later retry can preserve a previously committed level three"), F.Run->RestoreProgressionState(Completed));
    TestEqual(TEXT("Completed level three remains earned"), F.Run->GetPlayerDamageMultiplier(), 1.5f);
    FNLProgressionState Invalid = Completed;
    Invalid.UpgradeLevel = 4;
    TestFalse(TEXT("Unsupported saved level is rejected atomically"), F.Run->RestoreProgressionState(Invalid));
    TestEqual(TEXT("Invalid restore cannot change the final earned level"), F.Run->GetProgressionState().UpgradeLevel, 3);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLSecondUpgradeReentrantRewardTest,
    "Nilin.Progression.SecondUpgrade.CallbackSeesAtomicRewardAndMayRestoreEntrance", NLSecondUpgradeTests::Flags)
bool FNLSecondUpgradeReentrantRewardTest::RunTest(const FString& Parameters)
{
    using namespace NLSecondUpgradeTests;
    FRunFixture F;
    F.Run->AwardLingQi(TEXT("Committed.Entrance"), 99.0f);
    const FNLProgressionState Entry = F.Run->GetProgressionState();
    FNLProgressionState Observed;
    float ObservedMultiplier = 0.0f, ObservedAward = 0.0f;
    int32 Notifications = 0;
    bool bRepeatedAward = true, bRestoreSucceeded = false;
    F.Observe([&]()
    {
        ++Notifications;
        Observed = F.Run->GetProgressionState();
        ObservedMultiplier = F.Run->GetPlayerDamageMultiplier();
        ObservedAward = F.Run->GetLastLingQiAwardAmount();
        F.StopObserving();
        bRepeatedAward = F.Run->AwardLingQi(TEXT("Current.Threshold"), 1.0f);
        bRestoreSucceeded = F.Run->RestoreProgressionState(Entry);
    });
    TestTrue(TEXT("Outer reward commits before notifying real dynamic listeners"), F.Run->AwardLingQi(TEXT("Current.Threshold"), 1.0f));
    TestEqual(TEXT("Listener sees the final level, not an intermediate level two"), Observed.UpgradeLevel, 3);
    TestEqual(TEXT("Listener sees the matching earned currency"), Observed.LingQi, 100.0f);
    TestTrue(TEXT("Listener sees the committed unique event ID"), Observed.RewardedEventIds.Contains(TEXT("Current.Threshold")));
    TestEqual(TEXT("Listener sees the matching final damage effect"), ObservedMultiplier, 1.5f);
    TestEqual(TEXT("Listener sees the matching actual reward feedback"), ObservedAward, 1.0f);
    TestFalse(TEXT("Reentrant duplicate callback cannot mint more currency"), bRepeatedAward);
    TestTrue(TEXT("Reentrant retry may restore its immutable entry"), bRestoreSucceeded);
    TestEqual(TEXT("Outer reward cannot overwrite the reentrant restored level"), F.Run->GetProgressionState().UpgradeLevel, 2);
    TestEqual(TEXT("Outer reward cannot overwrite the reentrant restored currency"), F.Run->GetProgressionState().LingQi, 99.0f);
    TestEqual(TEXT("Outer reward cannot replay feedback after the restore"), F.Run->GetLastLingQiAwardAmount(), 0.0f);
    TestEqual(TEXT("Only the committed outer reward reached this listener"), Notifications, 1);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLSecondUpgradeReentrantFloorTest,
    "Nilin.Progression.SecondUpgrade.LevelFloorCallbackMayBeginNewRun", NLSecondUpgradeTests::Flags)
bool FNLSecondUpgradeReentrantFloorTest::RunTest(const FString& Parameters)
{
    using namespace NLSecondUpgradeTests;
    FRunFixture F;
    F.Run->AwardLingQi(TEXT("Earlier.Earned"), 1.0f);
    const FGuid NewRun = FGuid::NewGuid();
    FNLProgressionState Observed;
    F.Observe([&]()
    {
        Observed = F.Run->GetProgressionState();
        F.StopObserving();
        F.Run->BeginRun(NewRun);
    });
    TestTrue(TEXT("A valid floor commits before its listener begins another run"), F.Run->EnsureUpgradeLevel(3));
    TestEqual(TEXT("Listener sees the guaranteed level three"), Observed.UpgradeLevel, 3);
    TestEqual(TEXT("Listener sees no fabricated floor currency"), Observed.LingQi, 1.0f);
    TestTrue(TEXT("The new run identity survives return from the old floor"), F.Run->GetRunId() == NewRun);
    TestEqual(TEXT("The new run keeps its initial level"), F.Run->GetProgressionState().UpgradeLevel, 1);
    TestEqual(TEXT("The new run keeps zero currency"), F.Run->GetProgressionState().LingQi, 0.0f);
    TestEqual(TEXT("The new run receives no stale old-run effect"), F.Run->GetPlayerDamageMultiplier(), 1.0f);
    TestEqual(TEXT("The new run receives no stale old-run upgrade feedback"), F.Run->GetLastUpgradeTimeSeconds(), -1.0);
    return true;
}

#endif
