#if WITH_DEV_AUTOMATION_TESTS

#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/SphereComponent.h"
#include "CoreGlobals.h"
#include "Encounter/NLLevelEncounterDirector.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/PlayerState.h"
#include "GameFramework/WorldSettings.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/Paths.h"
#include "Pickup/NLOrdinarySupplyPickup.h"
#include "Progression/NLOrdinaryLootSubsystem.h"
#include "Progression/NLRunStateSubsystem.h"

namespace NLOrdinaryLootTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
    FString PathFor(FGuid Run, bool bMaster = false)
    {
        return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(),
            bMaster ? TEXT("SaveGames/NilinMasterRewards") : TEXT("SaveGames/NilinOrdinaryLoot"),
            Run.ToString(EGuidFormats::Digits) + (bMaster ? TEXT(".nlmr") : TEXT(".nllo"))));
    }
    FName Event(int32 Index) { return FName(*FString::Printf(TEXT("Test.Loot.A.Wave.01.Spawn.%04d"), Index)); }
    struct FWorld
    {
        UWorld* World = nullptr;
        UGameInstance* GameInstance = nullptr;
        UNLRunStateSubsystem* State = nullptr;
        UNLOrdinaryLootSubsystem* Loot = nullptr;
        TArray<FGuid> Runs;
        const uint64 SavedFrame = GFrameCounter;
        FWorld()
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game, false,
                FName(*FString::Printf(TEXT("NilinOrdinaryLoot_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits))),
                nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            GameInstance = NewObject<UGameInstance>(GEngine);
            World->SetGameInstance(GameInstance);
            FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
            Context.SetCurrentWorld(World);
            Context.OwningGameInstance = GameInstance;
            GameInstance->Init();
            State = GameInstance->GetSubsystem<UNLRunStateSubsystem>();
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            World->GetWorldSettings()->NotifyBeginPlay();
            Loot = World->GetSubsystem<UNLOrdinaryLootSubsystem>();
            if (State) NewRun();
        }
        FGuid NewRun()
        {
            const FGuid Run = FGuid::NewGuid();
            Runs.Add(Run);
            State->BeginRun(Run);
            return Run;
        }
        ~FWorld()
        {
            if (World)
            {
                World->EndPlay(EEndPlayReason::Quit);
                GEngine->DestroyWorldContext(World);
                World->DestroyWorld(false);
            }
            if (GameInstance) GameInstance->Shutdown();
            IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
            for (FGuid Run : Runs) for (bool bMaster : { false, true })
            {
                const FString Path = PathFor(Run, bMaster);
                Files.DeleteFile(*Path);
                Files.DeleteFile(*(Path + TEXT(".tmp")));
                Files.DeleteDirectory(*(Path + TEXT(".tmp")));
            }
            GFrameCounter = SavedFrame;
        }
        AActor* AddBody(ENLCombatFaction Faction, float Health)
        {
            AActor* Actor = World->SpawnActor<AActor>();
            if (!Actor) return nullptr;
            USphereComponent* Sphere = NewObject<USphereComponent>(Actor);
            Actor->SetRootComponent(Sphere);
            Actor->AddInstanceComponent(Sphere);
            Sphere->InitSphereRadius(25);
            Sphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
            Sphere->SetCollisionObjectType(ECC_Pawn);
            Sphere->SetCollisionResponseToAllChannels(ECR_Overlap);
            Sphere->SetGenerateOverlapEvents(true);
            Sphere->RegisterComponent();
            Actor->SetActorLocation(FVector(3000, 0, 100));
            UNLCombatIdentityComponent* Identity = NewObject<UNLCombatIdentityComponent>(Actor);
            Actor->AddInstanceComponent(Identity);
            Identity->Faction = Faction;
            Identity->RegisterComponent();
            UNLCombatVitalsComponent* Vitals = NewObject<UNLCombatVitalsComponent>(Actor);
            Actor->AddInstanceComponent(Vitals);
            Vitals->RegisterComponent();
            Vitals->MaxHealth = 100;
            Vitals->ResetVitals();
            Vitals->Health = Health;
            return Actor;
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLOrdinaryLootPityTest,
    "Nilin.Progression.OrdinaryLoot.FifthEligibleRollAndProbabilityBoundaries", NLOrdinaryLootTests::Flags)

bool FNLOrdinaryLootPityTest::RunTest(const FString& Parameters)
{
    using namespace NLOrdinaryLootTests;
    using K = ENLOrdinarySupplyKind;
    TestEqual(TEXT("Twenty-percent success boundary is exclusive"), UNLOrdinaryLootSubsystem::EvaluateRoll(.2f, 0, 0, .2f), K::None);
    TestEqual(TEXT("A roll below twenty percent drops small healing"), UNLOrdinaryLootSubsystem::EvaluateRoll(.199f, .799f, 0, .2f), K::Small);
    TestEqual(TEXT("The upper twenty percent of sizes is large"), UNLOrdinaryLootSubsystem::EvaluateRoll(.1f, .8f, 0, .2f), K::Large);
    TestEqual(TEXT("Four misses override even a failed drop roll"), UNLOrdinaryLootSubsystem::EvaluateRoll(.99f, .2f, 4, 0), K::Small);
    TestEqual(TEXT("Small supply restores ten"), UNLOrdinaryLootSubsystem::HealthForKind(K::Small), 10.f);
    TestEqual(TEXT("Large supply restores twenty"), UNLOrdinaryLootSubsystem::HealthForKind(K::Large), 20.f);
    FWorld Scope;
    if (!TestTrue(TEXT("World services"), Scope.State && Scope.Loot)) return false;
    TestTrue(TEXT("An empty isolated run accepts a zero-percent fixture"), Scope.Loot->ConfigureDropRules(0, 1105));
    for (int32 Index = 0; Index < 4; ++Index)
    {
        TestTrue(TEXT("Eligible miss is committed"), Scope.Loot->RecordEligibleDefeat(Event(Index), FVector(Index * 100, 0, 100)));
        TestEqual(TEXT("Consecutive misses accumulate once"), Scope.Loot->GetConsecutiveMisses(), Index + 1);
        TestTrue(TEXT("Duplicate no-drop event succeeds idempotently"), Scope.Loot->RecordEligibleDefeat(Event(Index), FVector(999)));
        TestEqual(TEXT("Duplicate miss cannot advance pity"), Scope.Loot->GetConsecutiveMisses(), Index + 1);
    }
    TestTrue(TEXT("The fifth eligible result commits a forced supply"), Scope.Loot->RecordEligibleDefeat(Event(4), FVector(0, 500, 100)));
    TestTrue(TEXT("The fifth result is a healing item"), Scope.Loot->GetSupplyKind(Event(4)) != K::None);
    TestNotNull(TEXT("The committed fifth result has an actual pickup"), Scope.Loot->GetPendingSupply(Event(4)));
    TestEqual(TEXT("Success resets consecutive misses"), Scope.Loot->GetConsecutiveMisses(), 0);
    TestEqual(TEXT("Only five unique events were processed"), Scope.Loot->GetProcessedCount(), 5);
    TestFalse(TEXT("Production rules cannot be changed after first commit"), Scope.Loot->ConfigureDropRules(1, 99));
    TestTrue(TEXT("A later miss restarts the counter"), Scope.Loot->RecordEligibleDefeat(Event(5), FVector(0, 600, 100)));
    TestEqual(TEXT("Post-drop miss count is one"), Scope.Loot->GetConsecutiveMisses(), 1);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLOrdinaryLootPersistenceTest,
    "Nilin.Progression.OrdinaryLoot.CommitFailureRollbackAndRunIsolation", NLOrdinaryLootTests::Flags)

bool FNLOrdinaryLootPersistenceTest::RunTest(const FString& Parameters)
{
    using namespace NLOrdinaryLootTests;
    FWorld Scope;
    if (!TestTrue(TEXT("World services"), Scope.State && Scope.Loot)) return false;
    const FGuid FirstRun = Scope.State->GetRunId();
    const FNLProgressionState OldCheckpoint = Scope.State->GetProgressionState();
    TestTrue(TEXT("Isolated guaranteed-drop fixture"), Scope.Loot->ConfigureDropRules(1, 5));
    IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
    const FString Temp = PathFor(FirstRun) + TEXT(".tmp");
    TestTrue(TEXT("Create the test ledger parent directory"), Files.CreateDirectoryTree(*FPaths::GetPath(Temp)));
    TestTrue(TEXT("Test exclusively blocks its own temporary output path"), Files.CreateDirectory(*Temp));
    const int32 BeforeRandom = Scope.Loot->RandomState;
    TestFalse(TEXT("Failed persistence rejects a new result"), Scope.Loot->RecordEligibleDefeat(Event(0), FVector(0, 0, 100)));
    TestEqual(TEXT("Failed commit does not advance random state"), Scope.Loot->RandomState, BeforeRandom);
    TestEqual(TEXT("Failed commit does not advance misses"), Scope.Loot->GetConsecutiveMisses(), 0);
    TestEqual(TEXT("Failed commit does not install a processed event"), Scope.Loot->GetProcessedCount(), 0);
    TestTrue(TEXT("Remove only the exact test-owned empty blocker"), Files.DeleteDirectory(*Temp));
    TestTrue(TEXT("The same event can recover after IO resumes"), Scope.Loot->RecordEligibleDefeat(Event(0), FVector(0, 0, 100)));
    ANLOrdinarySupplyPickup* Pickup = Scope.Loot->GetPendingSupply(Event(0));
    if (!TestNotNull(TEXT("Committed actual supply"), Pickup)) return false;
    const float Health = Pickup->GetHealthAmount();
    AActor* Player = Scope.AddBody(ENLCombatFaction::Player, 30);
    if (!TestNotNull(TEXT("Injured player"), Player)) return false;
    UNLCombatVitalsComponent* Vitals = Player->FindComponentByClass<UNLCombatVitalsComponent>();
    TestTrue(TEXT("Block claim IO with a test-owned temporary directory"), Files.CreateDirectory(*Temp));
    TestFalse(TEXT("Failed claim grants no healing"), Pickup->TryCollect(Player));
    TestEqual(TEXT("Failed claim preserves health"), Vitals->GetHealth(), 30.f);
    TestFalse(TEXT("Failed claim is not installed"), Scope.Loot->HasCollectedSupply(Event(0)));
    TestEqual(TEXT("Failed claim leaves the same pickup"), Scope.Loot->GetPendingSupply(Event(0)), Pickup);
    TestTrue(TEXT("Clear the exact claim IO blocker"), Files.DeleteDirectory(*Temp));
    TestTrue(TEXT("A committed claim heals"), Pickup->TryCollect(Player));
    TestEqual(TEXT("Health gain matches committed size"), Vitals->GetHealth(), 30.f + Health);
    TestTrue(TEXT("Claim is durable"), Scope.Loot->HasCollectedSupply(Event(0)));
    TestTrue(TEXT("Restoring a pre-defeat checkpoint succeeds"), Scope.State->RestoreProgressionState(OldCheckpoint));
    TestTrue(TEXT("Old checkpoint cannot clear the independent claim"), Scope.Loot->HasCollectedSupply(Event(0)));
    const FGuid SecondRun = Scope.NewRun();
    TestEqual(TEXT("New run has no inherited ordinary events"), Scope.Loot->GetProcessedCount(), 0);
    TestEqual(TEXT("New run has no inherited misses"), Scope.Loot->GetConsecutiveMisses(), 0);
    TestTrue(TEXT("Second run may tune its own first roll"), Scope.Loot->ConfigureDropRules(1, 17));
    TestTrue(TEXT("Same stable event is independent in a new run"), Scope.Loot->RecordEligibleDefeat(Event(0), FVector(500, 0, 100)));
    TestNotNull(TEXT("New run owns a new pending pickup"), Scope.Loot->GetPendingSupply(Event(0)));
    Scope.State->BeginRun(FirstRun);
    TestEqual(TEXT("A real disk reload recovers the original event count"), Scope.Loot->GetProcessedCount(), 1);
    TestTrue(TEXT("A real disk reload recovers the old claim"), Scope.Loot->HasCollectedSupply(Event(0)));
    TestNull(TEXT("Reload cannot respawn the collected supply"), Scope.Loot->GetPendingSupply(Event(0)));
    TestTrue(TEXT("Repeated old event does not roll again"), Scope.Loot->RecordEligibleDefeat(Event(0), FVector(999)));
    TestEqual(TEXT("Repeated old result retains original event count"), Scope.Loot->GetProcessedCount(), 1);
    Scope.State->BeginRun(SecondRun);
    TestNotNull(TEXT("Pending supply restores from its own new-run ledger"), Scope.Loot->GetPendingSupply(Event(0)));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLOrdinaryLootPickupTest,
    "Nilin.Progression.OrdinaryLoot.LivingPlayerPauseOverlapAndPendingRestore", NLOrdinaryLootTests::Flags)

bool FNLOrdinaryLootPickupTest::RunTest(const FString& Parameters)
{
    using namespace NLOrdinaryLootTests;
    FWorld Scope;
    if (!TestTrue(TEXT("World services"), Scope.State && Scope.Loot)) return false;
    TestTrue(TEXT("Guaranteed-drop fixture before any commit"), Scope.Loot->ConfigureDropRules(1, 3));
    TestTrue(TEXT("First supply record"), Scope.Loot->RecordEligibleDefeat(Event(0), FVector(0, 0, 100)));
    ANLOrdinarySupplyPickup* Pickup = Scope.Loot->GetPendingSupply(Event(0));
    if (!TestNotNull(TEXT("Actual supply"), Pickup)) return false;
    AActor* Player = Scope.AddBody(ENLCombatFaction::Player, 100);
    AActor* Enemy = Scope.AddBody(ENLCombatFaction::Enemy, 20);
    if (!TestTrue(TEXT("Test bodies"), Player && Enemy)) return false;
    UNLCombatVitalsComponent* Vitals = Player->FindComponentByClass<UNLCombatVitalsComponent>();
    TestFalse(TEXT("Nonplayer cannot consume a supply"), Pickup->TryCollect(Enemy));
    TestFalse(TEXT("Full-health player leaves it intact"), Pickup->TryCollect(Player));
    Vitals->Health = 0;
    TestFalse(TEXT("Dead player cannot revive from it"), Pickup->TryCollect(Player));
    Vitals->Health = 95;
    APlayerState* Pauser = Scope.World->SpawnActor<APlayerState>();
    Scope.World->GetWorldSettings()->SetPauserPlayerState(Pauser);
    TestTrue(TEXT("The test world is paused"), Scope.World->IsPaused());
    TestFalse(TEXT("Paused world cannot consume it"), Pickup->TryCollect(Player));
    Scope.World->GetWorldSettings()->SetPauserPlayerState(nullptr);
    TestFalse(TEXT("All rejected collections remain unclaimed"), Scope.Loot->HasCollectedSupply(Event(0)));
    Pickup->Destroy();
    Scope.Loot->RestorePendingSupplies();
    Pickup = Scope.Loot->GetPendingSupply(Event(0));
    if (!TestNotNull(TEXT("Unclaimed actor loss rebuilds the durable pending supply"), Pickup)) return false;
    TestEqual(TEXT("Pending rebuild retains original location"), Pickup->GetActorLocation(), FVector(0, 0, 100));
    Player->SetActorLocation(Pickup->GetActorLocation());
    ++GFrameCounter;
    Scope.World->Tick(LEVELTICK_All, .02f);
    TestEqual(TEXT("Actual pawn overlap heals only up to maximum health"), Vitals->GetHealth(), 100.f);
    TestTrue(TEXT("Actual overlap commits exactly one claim"), Scope.Loot->HasCollectedSupply(Event(0)));
    TestEqual(TEXT("Feedback reports actual five-point healing"), Scope.Loot->GetLastCollectedHealth(), 5.f);
    Scope.Loot->RestorePendingSupplies();
    TestNull(TEXT("Claimed supply does not return"), Scope.Loot->GetPendingSupply(Event(0)));
    TestFalse(TEXT("Repeated public claim cannot heal again"), Scope.Loot->TryCollect(Event(0), Player));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLOrdinaryLootEligibilityTest,
    "Nilin.Progression.OrdinaryLoot.MasterBossExclusionAndGuardEligibility", NLOrdinaryLootTests::Flags)

bool FNLOrdinaryLootEligibilityTest::RunTest(const FString& Parameters)
{
    FNLLevelEncounterStage Stage;
    Stage.StageId = TEXT("GM02");
    Stage.MasterId = TEXT("GM02");
    TestTrue(TEXT("First master's guard is eligible"), ANLLevelEncounterDirector::IsOrdinarySupplyEligible(Stage, 0, 3, 0, 2));
    TestTrue(TEXT("Second master's guard is eligible"), ANLLevelEncounterDirector::IsOrdinarySupplyEligible(Stage, 1, 3, 0, 2));
    TestFalse(TEXT("Final master body cannot consume an ordinary roll"), ANLLevelEncounterDirector::IsOrdinarySupplyEligible(Stage, 2, 3, 1, 2));
    Stage.StageId = TEXT("Boss");
    Stage.MasterId = NAME_None;
    TestFalse(TEXT("Boss body uses fixed rewards"), ANLLevelEncounterDirector::IsOrdinarySupplyEligible(Stage, 0, 1, 0, 1));
    Stage.StageId = TEXT("Ainside");
    TestTrue(TEXT("Ordinary final wave enemy remains eligible"), ANLLevelEncounterDirector::IsOrdinarySupplyEligible(Stage, 5, 6, 0, 1));
    TestFalse(TEXT("Invalid ordinal cannot consume a roll"), ANLLevelEncounterDirector::IsOrdinarySupplyEligible(Stage, -1, 6, 0, 1));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLOrdinaryLootCorruptLedgerTest,
    "Nilin.Progression.OrdinaryLoot.CorruptLedgerIsRejectedWithoutReroll", NLOrdinaryLootTests::Flags)

bool FNLOrdinaryLootCorruptLedgerTest::RunTest(const FString& Parameters)
{
    using namespace NLOrdinaryLootTests;
    FWorld Scope;
    if (!TestTrue(TEXT("World services"), Scope.State && Scope.Loot)) return false;
    const FGuid Original = Scope.State->GetRunId();
    TestTrue(TEXT("Write the original isolated ledger"), Scope.Loot->RecordEligibleDefeat(Event(0), FVector(0, 0, 100)));
    Scope.NewRun();
    IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
    const FString Path = PathFor(Original);
    {
        const uint8 BadHeader[8] = { 0, 1, 2, 3, 4, 5, 6, 7 };
        TUniquePtr<IFileHandle> Handle(Files.OpenWrite(*Path, false, false));
        if (!TestTrue(TEXT("Open only this test run's old ledger"), Handle.IsValid())) return false;
        TestTrue(TEXT("Install a deliberately truncated test record"), Handle->Write(BadHeader, sizeof(BadHeader)) && Handle->Flush(true));
    }
    Scope.State->BeginRun(Original);
    TestEqual(TEXT("Corrupt persistence has a clear failure"), Scope.Loot->GetLastFailureReason(), FName(TEXT("OrdinaryLootLedgerCorrupt")));
    TestFalse(TEXT("Corrupt run cannot reset and reroll an old event"), Scope.Loot->RecordEligibleDefeat(Event(0), FVector(999)));
    TestEqual(TEXT("The damaged file is preserved for diagnosis"), Files.FileSize(*Path), static_cast<int64>(8));
    TestEqual(TEXT("No supply actor is guessed from corrupt state"), Scope.Loot->GetPendingSupplies().Num(), 0);
    return true;
}

#endif
