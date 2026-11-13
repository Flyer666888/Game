#if WITH_DEV_AUTOMATION_TESTS

#include "AI/NLEnemyCharacter.h"
#include "Camera/CameraComponent.h"
#include "Combat/NLAbilityComponent.h"
#include "Combat/NLAttackDefinition.h"
#include "Combat/NLBladeComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "CoreGlobals.h"
#include "Encounter/NLEncounterController.h"
#include "Encounter/NLLevelEncounterDirector.h"
#include "Encounter/NLWaveDefinition.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/WorldSettings.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "MotionControllerComponent.h"
#include "Objective/NLRitualObjective.h"
#include "Player/NLVRGameMode.h"
#include "Player/NLVRPlayerCharacter.h"
#include "Progression/NLRunStateSubsystem.h"
#include "Progression/NLUpgradeDefinition.h"

namespace NLVRLevelFlowTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

    /** Runs the real VR GameMode StartPlay and Pawn BeginPlay, with no XR device or rendered frames.
     *  Only this fixture's unique level marker and run ledger may be removed. */
    struct FScopedWorld
    {
        UWorld* World = nullptr;
        UGameInstance* Instance = nullptr;
        UNLRunStateSubsystem* Run = nullptr;
        ANLVRPlayerCharacter* Player = nullptr;
        ANLLevelEncounterDirector* Director = nullptr;
        ANLEncounterController* Lab = nullptr;
        ANLRitualObjective* Objective = nullptr;
        FName LevelId;
        FGuid RunId;
        const uint64 SavedFrameCounter = GFrameCounter;

        FScopedWorld(bool bWithLevel, bool bWithObjective = false)
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game, false,
                FName(*FString::Printf(TEXT("VRLevelFlow_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits))),
                nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            Instance = NewObject<UGameInstance>(GEngine);
            World->SetGameInstance(Instance);
            FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
            Context.SetCurrentWorld(World);
            Context.OwningGameInstance = Instance;
            Instance->Init();
            Run = Instance->GetSubsystem<UNLRunStateSubsystem>();

            FURL URL;
            URL.AddOption(TEXT("game=/Script/experiment.NLVRGameMode"));
            if (!World->SetGameMode(URL)) return;

            FNLLevelEncounterStage Stage;
            Stage.StageId = TEXT("Test.Entry");
            Stage.InstructionText = FText::FromString(TEXT("DESKTOP_ONLY_PRESS_Q"));
            Stage.TriggerCenter = FVector(0, 0, 88);
            Stage.TriggerExtent = FVector(600);
            Stage.EntryTransform = FTransform(FRotator(0, 35, 0), FVector(35, 20, 108));
            Stage.WarningSeconds = 20.0f;
            FNLWaveSpawnPoint Point;
            Point.SpawnPointId = TEXT("Test.Point");
            Point.SpawnTransform.SetLocation(FVector(400, 0, 100));
            Stage.SpawnPoints.Add(Point);
            UNLWaveDefinition* Wave = NewObject<UNLWaveDefinition>(World);
            Wave->WaveId = TEXT("Test.Wave");
            FNLWaveSpawnEntry Entry;
            Entry.EntryId = TEXT("Test.Enemy");
            Entry.EnemyClass = ANLEnemyCharacter::StaticClass();
            Entry.Count = 1;
            Entry.SpawnPointIds.Add(Point.SpawnPointId);
            Wave->SpawnEntries.Add(Entry);
            Stage.Waves.Add(Wave);

            if (bWithLevel)
            {
                if (bWithObjective)
                {
                    Stage.ObjectiveStableId = TEXT("Test.VRLevel.Ritual");
                    Objective = World->SpawnActorDeferred<ANLRitualObjective>(ANLRitualObjective::StaticClass(),
                        FTransform::Identity, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
                    if (!Objective) return;
                    Objective->ObjectiveStableId = Stage.ObjectiveStableId;
                    Objective->bStartActive = false;
                    Objective->FinishSpawning(FTransform::Identity);
                }
                LevelId = FName(*FString::Printf(TEXT("Test.VRLevel.%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits)));
                Director = World->SpawnActorDeferred<ANLLevelEncounterDirector>(ANLLevelEncounterDirector::StaticClass(),
                    FTransform::Identity, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
                if (!Director) return;
                Director->LevelId = LevelId;
                Director->Stages.Add(Stage);
                Director->UpgradeDefinition = NewObject<UNLUpgradeDefinition>(Director);
                Director->FinishSpawning(FTransform::Identity);
            }
            // A valid unrelated lab deliberately exists in the level fixture. Level routing
            // must not fall back to this controller during warning or traversal.
            Lab = World->SpawnActorDeferred<ANLEncounterController>(ANLEncounterController::StaticClass(),
                FTransform::Identity, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
            if (!Lab) return;
            Lab->Waves = Stage.Waves;
            Lab->SpawnPoints = Stage.SpawnPoints;
            Lab->bEnableCheckpoints = false;
            Lab->bShowReadyPreviews = false;
            Lab->FinishSpawning(FTransform::Identity);
            FActorSpawnParameters Parameters;
            Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
            Player = World->SpawnActor<ANLVRPlayerCharacter>(FVector(0, 0, 88), FRotator::ZeroRotator, Parameters);
            World->InitializeActorsForPlay(URL);
            World->BeginPlay();
            RunId = Run ? Run->GetRunId() : FGuid();
            if (Player)
            {
                Player->SetActorTickEnabled(false);
                Player->LeftController->SetComponentTickEnabled(false);
                Player->RightController->SetComponentTickEnabled(false);
            }
        }

        ~FScopedWorld()
        {
            if (World)
            {
                World->EndPlay(EEndPlayReason::Quit);
                GEngine->DestroyWorldContext(World);
                World->DestroyWorld(false);
            }
            if (Instance) Instance->Shutdown();
            IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
            if (!LevelId.IsNone())
            {
                const FString Name = LevelId.ToString().ToLower();
                const FTCHARToUTF8 Utf8(*Name);
                FSHAHash Hash;
                FSHA1::HashBuffer(Utf8.Get(), Utf8.Length(), Hash.Hash);
                const FString Path = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(),
                    TEXT("SaveGames/NilinLevelRuns"), Hash.ToString() + TEXT(".nlrun")));
                Files.DeleteFile(*Path);
                Files.DeleteFile(*(Path + TEXT(".tmp")));
            }
            if (RunId.IsValid())
            {
                const FString Path = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(),
                    TEXT("SaveGames/NilinMasterRewards"), RunId.ToString(EGuidFormats::Digits) + TEXT(".nlmr")));
                Files.DeleteFile(*Path);
                Files.DeleteFile(*(Path + TEXT(".tmp")));
            }
            GFrameCounter = SavedFrameCounter;
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLVRLevelRoutingTest,
    "Nilin.VR.LevelFlow.StartupRoutingAndLabFallback", NLVRLevelFlowTests::Flags)

bool FNLVRLevelRoutingTest::RunTest(const FString& Parameters)
{
    using namespace NLVRLevelFlowTests;
    {
        FScopedWorld Scope(true);
        if (!TestNotNull(TEXT("VR level pawn"), Scope.Player) || !TestNotNull(TEXT("Level director"), Scope.Director)
            || !TestNotNull(TEXT("Run subsystem"), Scope.Run) || !TestNotNull(TEXT("Unrelated lab"), Scope.Lab)) return false;
        const ANLVRGameMode* Mode = Scope.World->GetAuthGameMode<ANLVRGameMode>();
        if (!TestNotNull(TEXT("Actual VR GameMode started the world"), Mode)) return false;
        TestTrue(TEXT("Level VR omits laboratory canvas keyboard instructions"), Mode->HUDClass == nullptr);
        TestTrue(TEXT("VR level startup creates an isolated run without a pawn tick"), Scope.Run->GetRunId().IsValid());
        TestTrue(TEXT("Director configured growth in native BeginPlay"), Scope.Run->GetUpgradeDefinition() != nullptr);
        TestNull(TEXT("Traversal must not bind the unrelated ready lab"), Scope.Player->GetEncounterController());
        APlayerController* Controller = Scope.World->SpawnActor<APlayerController>();
        if (!TestNotNull(TEXT("Controller used by actual automatic region lookup"), Controller)) return false;
        Controller->Possess(Scope.Player);
        TestFalse(TEXT("No physical XR tracking never reports entry ready"), Scope.Player->IsReadyForLevelEncounter());
        Scope.Director->Tick(0.1f);
        TestEqual(TEXT("Automatic region entry waits for VR readiness"),
            Scope.Director->GetStageStatus(TEXT("Test.Entry")), ENLLevelStageState::Available);
        Scope.Player->RequestEncounterToggle();
        TestEqual(TEXT("Manual start cannot start the unrelated lab"), Scope.Lab->GetState(), ENLEncounterState::Ready);
        TestEqual(TEXT("Manual start does not bypass the region gate"),
            Scope.Director->GetStageStatus(TEXT("Test.Entry")), ENLLevelStageState::Available);
        Scope.Player->bInitialAutoStartPending = true;
        Scope.Player->UpdateInitialAutoStart(0.1f);
        TestFalse(TEXT("Level flow consumes laboratory auto-start intent"), Scope.Player->bInitialAutoStartPending);
        TestTrue(TEXT("Explicit rule-test entry may prepare a warning"), Scope.Director->TryActivateStage(TEXT("Test.Entry"), Scope.Player));
        TestNull(TEXT("Warning still ignores the unrelated lab"), Scope.Player->GetEncounterController());
        Scope.Player->RequestEncounterToggle();
        TestEqual(TEXT("Start/cancel cannot cancel the level warning"),
            Scope.Director->GetStageStatus(TEXT("Test.Entry")), ENLLevelStageState::Warning);
        const float WarningBefore = Scope.Director->GetWarningRemaining();
        for (int32 Frame = 0; Frame < 25; ++Frame)
        {
            ++GFrameCounter;
            Scope.World->Tick(LEVELTICK_All, 1.0f);
        }
        Scope.Director->Tick(0.1f);
        TestEqual(TEXT("Explicit entry still cannot spawn combat without VR readiness"),
            Scope.Director->GetStageStatus(TEXT("Test.Entry")), ENLLevelStageState::Warning);
        TestNull(TEXT("No encounter is generated while the headset is unavailable"), Scope.Director->GetActiveEncounter());
        TestTrue(TEXT("Unready warning keeps its preparation time"),
            FMath::IsNearlyEqual(Scope.Director->GetWarningRemaining(), WarningBefore));
        const FString Status = Scope.Player->GetLevelProgressStatus();
        TestTrue(TEXT("VR status identifies the authored area"), Status.Contains(TEXT("Test.Entry")));
        TestTrue(TEXT("VR status exposes growth"), Status.Contains(TEXT("LING QI")));
        TestTrue(TEXT("VR status exposes four-seal ownership"), Status.Contains(TEXT("SEALS:")));
        TestFalse(TEXT("Desktop key instructions never enter VR status"), Status.Contains(TEXT("DESKTOP_ONLY")));
        TestTrue(TEXT("VR explains why entry is waiting"), Status.Contains(TEXT("WAITING FOR HEADSET + BOTH CONTROLLERS")));
        TestEqual(TEXT("VR keeps its own movement speed"), Scope.Player->GetCharacterMovement()->MaxWalkSpeed, Scope.Player->VRWalkSpeed);

        // Unit inputs for the readiness policy only: no XR provider/device is installed or emulated.
        // The actual no-device automatic-entry boundary was exercised above.
        Scope.Player->ANLDesktopPlayerCharacter::Tick(0.01f);
        Scope.Player->bHMDTrackingActive = true;
        Scope.Player->bLeftControllerTracked = Scope.Player->bRightControllerTracked = true;
        Scope.Player->bInputBindingsReady = Scope.Player->bInputMappingInstalled = true;
        Scope.Player->bRecenterPending = false;
        for (int32 Frame = 0; Frame < 11; ++Frame) Scope.Player->UpdateLevelEntryReadiness(0.25f);
        TestFalse(TEXT("Less than three continuous ready seconds cannot enter"), Scope.Player->IsReadyForLevelEncounter());
        Scope.Player->UpdateLevelEntryReadiness(0.25f);
        TestTrue(TEXT("Three continuous ready seconds permit entry"), Scope.Player->IsReadyForLevelEncounter());
        Scope.Player->bRightControllerTracked = false;
        Scope.Player->UpdateLevelEntryReadiness(0.1f);
        TestFalse(TEXT("A missing hand clears the ready interval"), Scope.Player->IsReadyForLevelEncounter());
        TestEqual(TEXT("Missing tracking restarts the full countdown"), Scope.Player->LevelEntryReadyElapsed, 0.0f);
    }
    {
        FScopedWorld Scope(false);
        if (!TestNotNull(TEXT("VR lab pawn"), Scope.Player) || !TestNotNull(TEXT("Lab run subsystem"), Scope.Run)
            || !TestNotNull(TEXT("Lab controller"), Scope.Lab)) return false;
        TestFalse(TEXT("A lab never opens the main level profile"), Scope.Run->GetRunId().IsValid());
        const ANLVRGameMode* Mode = Scope.World->GetAuthGameMode<ANLVRGameMode>();
        if (!TestNotNull(TEXT("Laboratory VR GameMode"), Mode)) return false;
        TestTrue(TEXT("Laboratory retains its existing canvas HUD"), Mode->HUDClass != nullptr);
        TestNull(TEXT("Lab has no level director"), Scope.Player->GetLevelDirector());
        TestTrue(TEXT("No-director routing preserves laboratory controller"), Scope.Player->GetEncounterController() == Scope.Lab);
        TestTrue(TEXT("Lab retains its one-shot auto-start intent"), Scope.Player->bInitialAutoStartPending);
        Scope.Player->Vitals->ApplyCombatDamage(10.0f);
        Scope.Player->ResetLab();
        TestEqual(TEXT("No-director reset preserves ready lab state"), Scope.Lab->GetState(), ENLEncounterState::Ready);
        TestEqual(TEXT("No-director reset restores lab health"), Scope.Player->Vitals->GetHealth(), Scope.Player->Vitals->GetMaxHealth());
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLVRLevelRetryTest,
    "Nilin.VR.LevelFlow.RetryGrowthProjectilesAndTracking", NLVRLevelFlowTests::Flags)

bool FNLVRLevelRetryTest::RunTest(const FString& Parameters)
{
    using namespace NLVRLevelFlowTests;
    FScopedWorld Scope(true);
    ANLVRPlayerCharacter* Player = Scope.Player;
    if (!TestNotNull(TEXT("VR pawn"), Player) || !TestNotNull(TEXT("Director"), Scope.Director)
        || !TestNotNull(TEXT("Run"), Scope.Run)) return false;
    TestTrue(TEXT("Entry growth"), Scope.Run->AwardLingQi(TEXT("Test.BeforeArea"), 7.0f));
    Player->Abilities->RestoreAbilityState(20.0f);
    TestTrue(TEXT("Enter the authored region"), Scope.Director->TryActivateStage(TEXT("Test.Entry"), Player));
    TestTrue(TEXT("Failed-attempt growth crosses the upgrade threshold"), Scope.Run->AwardLingQi(TEXT("Test.FailedAttempt"), 40.0f));
    Player->Abilities->RestoreAbilityState(85.0f);
    Player->Vitals->ApplyCombatDamage(Player->Vitals->GetMaxHealth());
    TestEqual(TEXT("Death fails the actual director stage"),
        Scope.Director->GetStageStatus(TEXT("Test.Entry")), ENLLevelStageState::Failed);

    UNLAttackDefinition* Attack = NewObject<UNLAttackDefinition>(Scope.World);
    Attack->StableId = TEXT("Test.VRLevel.Projectile");
    FActorSpawnParameters ParametersForProjectile;
    ParametersForProjectile.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    ANLCombatProjectile* Projectile = Scope.World->SpawnActor<ANLCombatProjectile>(
        FVector(100, 0, 150), FRotator::ZeroRotator, ParametersForProjectile);
    if (!TestNotNull(TEXT("Old projectile"), Projectile)) return false;
    TestTrue(TEXT("Projectile has a real attack identity"), Projectile->InitializeProjectile(Player, Attack, FVector::ForwardVector, 500, 5));

    // Supply tracking-space values directly, never emulate or poll a physical XR device.
    // A restore must discard every pending input and align this retained head pose at the safe entry.
    Player->bHMDTrackingActive = true;
    Player->bTrackedCombatEnabled = true;
    Player->bGuardInputHeld = true;
    Player->bGuardNeedsRelease = false;
    Player->HeadTrackingPosition = FVector(25, 10, 170);
    Player->HeadTrackingRotation = FRotator(0, 70, 0).Quaternion();
    Player->MoveAxis = FVector2D(1, 1);
    Player->TurnAxis = 1.0f;
    Player->VROrigin->SetRelativeLocation(FVector(150, 50, -88));
    Player->BladeQiInput.Release();
    TestTrue(TEXT("Pending pre-restore gesture exists"), Player->BladeQiInput.Press(Scope.World->GetTimeSeconds(), 0.25, true));
    Player->HandleKeyboardReset();

    const FNLProgressionState Growth = Scope.Run->GetProgressionState();
    TestEqual(TEXT("Retry restores entry LingQi"), Growth.LingQi, 7.0f);
    TestEqual(TEXT("Retry rolls back failed-attempt upgrade"), Growth.UpgradeLevel, 1);
    TestEqual(TEXT("Retry restores burst energy"), Player->Abilities->GetBurstEnergy(), 20.0f);
    TestFalse(TEXT("Failed-attempt reward ID is rolled back"), Growth.RewardedEventIds.Contains(TEXT("Test.FailedAttempt")));
    TestEqual(TEXT("Retry restarts the same area's warning"), Scope.Director->GetStageStatus(TEXT("Test.Entry")), ENLLevelStageState::Warning);
    TestEqual(TEXT("Retry restores the authored safe position"), Player->GetActorLocation(), FVector(35, 20, 108));
    TestTrue(TEXT("Retry destroys old projectile"), Projectile->IsActorBeingDestroyed());
    TestFalse(TEXT("Pending gesture cannot fire after teleport"), Player->BladeQiInput.HasPending(Scope.World->GetTimeSeconds()));
    TestTrue(TEXT("Held trigger requires a fresh release"), Player->BladeQiInput.NeedsRelease());
    TestTrue(TEXT("Held guard requires a fresh release"), Player->bGuardNeedsRelease);
    TestFalse(TEXT("Tracking combat remains invalid until a fresh sample"), Player->bTrackedCombatEnabled);
    TestTrue(TEXT("Movement input is cleared"), Player->MoveAxis.IsNearlyZero());
    TestEqual(TEXT("Turn input is cleared"), Player->TurnAxis, 0.0f);
    TestFalse(TEXT("Valid retained head pose was recentered"), Player->bRecenterPending);
    const FVector Head = Player->VROrigin->GetComponentTransform().TransformPosition(Player->HeadTrackingPosition);
    TestTrue(TEXT("Room-scale head is over the safe entry capsule"), FVector::Dist2D(Head, Player->GetActorLocation()) < 0.01);
    TestFalse(TEXT("Retry does not advertise laboratory manual start"), Player->VRStartStatus.Contains(TEXT("TO START")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLVRLevelRetryPreflightTest,
    "Nilin.VR.LevelFlow.MissingObjectiveRejectsBeforePlayerMutation", NLVRLevelFlowTests::Flags)

bool FNLVRLevelRetryPreflightTest::RunTest(const FString& Parameters)
{
    using namespace NLVRLevelFlowTests;
    FScopedWorld Scope(true, true);
    ANLVRPlayerCharacter* Player = Scope.Player;
    if (!TestNotNull(TEXT("VR pawn"), Player) || !TestNotNull(TEXT("Director"), Scope.Director)
        || !TestNotNull(TEXT("Run"), Scope.Run) || !TestNotNull(TEXT("Ritual"), Scope.Objective)) return false;
    TestTrue(TEXT("Capture a real ritual stage entry"), Scope.Director->TryActivateStage(TEXT("Test.Entry"), Player));
    Scope.Run->AwardLingQi(TEXT("Test.ActiveAttempt"), 45.0f);
    Player->Abilities->RestoreAbilityState(85.0f);
    Player->Vitals->ApplyCombatDamage(10.0f);
    Player->SetActorLocation(FVector(95, 75, 108));
    const float HealthBefore = Player->Vitals->GetHealth();
    const FVector LocationBefore = Player->GetActorLocation();
    Scope.Objective->Destroy();
    Player->HandleKeyboardReset();
    TestEqual(TEXT("Rejected reset leaves the warning active"),
        Scope.Director->GetStageStatus(TEXT("Test.Entry")), ENLLevelStageState::Warning);
    TestEqual(TEXT("Rejected reset never heals the player"), Player->Vitals->GetHealth(), HealthBefore);
    TestEqual(TEXT("Rejected reset never teleports the player"), Player->GetActorLocation(), LocationBefore);
    TestEqual(TEXT("Rejected reset never rolls back growth"), Scope.Run->GetProgressionState().LingQi, 45.0f);
    TestEqual(TEXT("Rejected reset never changes burst energy"), Player->Abilities->GetBurstEnergy(), 85.0f);
    TestTrue(TEXT("VR exposes the pure preflight failure"), Player->VRStartStatus.Contains(TEXT("MissingStageObjective")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLVRLevelRetryCallbackTest,
    "Nilin.VR.LevelFlow.RestoreCallbackInvalidationPreservesPlayer", NLVRLevelFlowTests::Flags)

bool FNLVRLevelRetryCallbackTest::RunTest(const FString& Parameters)
{
    using namespace NLVRLevelFlowTests;
    FScopedWorld Scope(true, true);
    ANLVRPlayerCharacter* Player = Scope.Player;
    if (!TestNotNull(TEXT("VR pawn"), Player) || !TestNotNull(TEXT("Director"), Scope.Director)
        || !TestNotNull(TEXT("Run"), Scope.Run) || !TestNotNull(TEXT("Ritual"), Scope.Objective)) return false;
    TestTrue(TEXT("Ritual stage captures valid entry state"), Scope.Director->TryActivateStage(TEXT("Test.Entry"), Player));
    Scope.Run->AwardLingQi(TEXT("Test.BeforeRejectedRestore"), 45.0f);
    Player->Abilities->RestoreAbilityState(85.0f);
    Player->Vitals->ApplyCombatDamage(10.0f);
    Player->SetActorLocation(FVector(95, 75, 108));
    Player->MoveAxis = FVector2D(0.5, 1.0);
    Player->TurnAxis = 0.75f;
    Player->LevelEntryReadyElapsed = 1.25f;
    Player->BladeQiInput.Release();
    Player->BladeQiInput.Press(Scope.World->GetTimeSeconds(), 0.25, true);
    const float HealthBefore = Player->Vitals->GetHealth();
    const FVector LocationBefore = Player->GetActorLocation();
    const FTransform TrackingBefore = Player->VROrigin->GetRelativeTransform();
    const FNLProgressionState GrowthBefore = Scope.Run->GetProgressionState();
    ANLCombatProjectile* Projectile = Scope.World->SpawnActor<ANLCombatProjectile>();
    if (!TestNotNull(TEXT("Attack actor survives a rejected reset"), Projectile)) return false;

    // This is a real dynamic run-state listener using the engine's existing reflected
    // DestroyActor function. No test hook or gameplay bypass is added to production code.
    FScriptDelegate DestroyDuringRestore;
    DestroyDuringRestore.BindUFunction(Scope.Objective, FName(TEXT("K2_DestroyActor")));
    Scope.Run->OnRunStateChanged.Add(DestroyDuringRestore);
    Player->HandleKeyboardReset();
    Scope.Run->OnRunStateChanged.Remove(DestroyDuringRestore);

    TestTrue(TEXT("The synchronous restore callback destroyed the target"), Scope.Objective->IsActorBeingDestroyed());
    TestEqual(TEXT("Callback rejection preserves player health"), Player->Vitals->GetHealth(), HealthBefore);
    TestEqual(TEXT("Callback rejection preserves player position"), Player->GetActorLocation(), LocationBefore);
    TestTrue(TEXT("Callback rejection preserves tracking origin"), Player->VROrigin->GetRelativeTransform().Equals(TrackingBefore));
    TestEqual(TEXT("Owned LingQi state is restored to before the failed operation"), Scope.Run->GetProgressionState().LingQi, GrowthBefore.LingQi);
    TestEqual(TEXT("Owned upgrade is restored to before the failed operation"), Scope.Run->GetProgressionState().UpgradeLevel, GrowthBefore.UpgradeLevel);
    TestEqual(TEXT("Owned burst state is restored to before the failed operation"), Player->Abilities->GetBurstEnergy(), 85.0f);
    TestTrue(TEXT("Reward ledger retains the pre-operation claim"),
        Scope.Run->GetProgressionState().RewardedEventIds.Contains(TEXT("Test.BeforeRejectedRestore")));
    TestFalse(TEXT("Rejected operation does not clear attacks"), Projectile->IsActorBeingDestroyed());
    TestTrue(TEXT("Rejected operation preserves pending controller gesture"), Player->BladeQiInput.HasPending(Scope.World->GetTimeSeconds()));
    TestEqual(TEXT("Rejected operation preserves movement input"), Player->MoveAxis, FVector2D(0.5, 1.0));
    TestEqual(TEXT("Rejected operation preserves turn input"), Player->TurnAxis, 0.75f);
    TestEqual(TEXT("Rejected operation preserves entry readiness progress"), Player->LevelEntryReadyElapsed, 1.25f);
    TestTrue(TEXT("VR reports the callback failure"), Player->VRStartStatus.Contains(TEXT("MissingStageObjective")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLVRLevelPreparedRetryTest,
    "Nilin.VR.LevelFlow.PreparedRetryDoesNotRestoreGrowthTwice", NLVRLevelFlowTests::Flags)

bool FNLVRLevelPreparedRetryTest::RunTest(const FString& Parameters)
{
    using namespace NLVRLevelFlowTests;
    FScopedWorld Scope(true, true);
    if (!TestNotNull(TEXT("VR pawn"), Scope.Player) || !TestNotNull(TEXT("Director"), Scope.Director)
        || !TestNotNull(TEXT("Run"), Scope.Run) || !TestNotNull(TEXT("Ritual"), Scope.Objective)) return false;
    TestTrue(TEXT("Prepare actual objective stage"), Scope.Director->TryActivateStage(TEXT("Test.Entry"), Scope.Player));
    Scope.Run->AwardLingQi(TEXT("Test.BeforePreparedRetry"), 45.0f);
    Scope.Director->FailActiveStage(TEXT("Test.PrepareRetry"));
    TestTrue(TEXT("First transaction restores entry growth"), Scope.Director->RestoreRetryProgression());
    FScriptDelegate DestroyOnUnexpectedSecondRestore;
    DestroyOnUnexpectedSecondRestore.BindUFunction(Scope.Objective, FName(TEXT("K2_DestroyActor")));
    Scope.Run->OnRunStateChanged.Add(DestroyOnUnexpectedSecondRestore);
    const bool bRetried = Scope.Director->RetryActiveStage();
    Scope.Run->OnRunStateChanged.Remove(DestroyOnUnexpectedSecondRestore);
    TestTrue(TEXT("Prepared retry commits normally"), bRetried);
    TestFalse(TEXT("Commit emits no second growth restore callback"), Scope.Objective->IsActorBeingDestroyed());
    TestEqual(TEXT("Prepared retry returns to warning"), Scope.Director->GetStageStatus(TEXT("Test.Entry")), ENLLevelStageState::Warning);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLVRStandingEyeHeightTest,
    "Nilin.VR.View.StandingEyesCrouchHandsAndRetry", NLVRLevelFlowTests::Flags)

bool FNLVRStandingEyeHeightTest::RunTest(const FString& Parameters)
{
    using namespace NLVRLevelFlowTests;
    {
        FScopedWorld Scope(true);
        ANLVRPlayerCharacter* Player = Scope.Player;
        if (!TestNotNull(TEXT("Main-level VR pawn"), Player)) return false;
        const double ExpectedStandingEyeHeight = Player->LevelStandingEyeHeight;
        constexpr double PhysicalCrouchDepth = 45.0;
        const double ExpectedCrouchedEyeHeight = ExpectedStandingEyeHeight - PhysicalCrouchDepth;
        AActor* Ground = Scope.World->SpawnActor<AActor>();
        UBoxComponent* Floor = NewObject<UBoxComponent>(Ground);
        Ground->SetRootComponent(Floor);
        Ground->AddInstanceComponent(Floor);
        Floor->InitBoxExtent(FVector(1000, 1000, 10));
        Floor->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
        Floor->SetCollisionObjectType(ECC_WorldStatic);
        Floor->SetCollisionResponseToAllChannels(ECR_Block);
        Floor->RegisterComponent();
        Floor->SetWorldLocation(FVector(0, 0, -10));
        Player->SetActorLocation(FVector(0, 0, 91));

        // Supplied tracking-space poses exercise the real origin transform without
        // pretending to run a physical headset or changing the user's XR runtime.
        const FTransform CapsuleBefore = Player->GetActorTransform();
        const FTransform WeaponInGrip = Player->HeldWeapon->GetRelativeTransform();
        const FTransform HandInGrip = Player->RightHand->GetRelativeTransform();
        Player->RecenterFloorOrigin();
        TestFalse(TEXT("An unavailable headset cannot set standing height"), Player->bStandingHeightCalibrated);
        Player->bHMDTrackingActive = true;
        Player->HeadTrackingPosition = FVector::ZeroVector;
        Player->RecenterFloorOrigin();
        TestFalse(TEXT("An initial zero pose cannot consume calibration"), Player->bStandingHeightCalibrated);
        TestTrue(TEXT("Zero pose keeps recenter pending"), Player->bRecenterPending);

        Player->HeadTrackingPosition = FVector(25, -12, 135);
        Player->HeadTrackingRotation = FRotator(0, 32, 0).Quaternion();
        Player->PlayerCamera->bLockToHmd = true;
        Player->PlayerCamera->SetRelativeLocationAndRotation(Player->HeadTrackingPosition, Player->HeadTrackingRotation);
        Player->LeftController->SetRelativeLocation(FVector(45, -25, 100));
        Player->RightController->SetRelativeLocation(FVector(45, 25, 100));
        Player->RecenterFloorOrigin();
        TestTrue(TEXT("Valid standing pose is calibrated once"), Player->bStandingHeightCalibrated);
        TestFalse(TEXT("Calibrated view can enter readiness countdown"), Player->bRecenterPending);
        TestTrue(TEXT("Low tracked height is raised to the ground-based enemy eye height"),
            FMath::IsNearlyEqual(Player->PlayerCamera->GetComponentLocation().Z, ExpectedStandingEyeHeight, 0.1));
        TestTrue(TEXT("Calibration preserves real HMD camera lock"), Player->PlayerCamera->bLockToHmd);
        TestTrue(TEXT("Calibration never moves the collision capsule"), Player->GetActorTransform().Equals(CapsuleBefore));
        TestTrue(TEXT("Right hand retains its corrected grip orientation"), Player->RightHand->GetRelativeTransform().Equals(HandInGrip));
        TestTrue(TEXT("Sword keeps its authored grip transform"), Player->HeldWeapon->GetRelativeTransform().Equals(WeaponInGrip));
        for (UMotionControllerComponent* Hand : {Player->LeftController.Get(), Player->RightController.Get()})
            TestTrue(TEXT("Both hands keep the physical 35 cm height difference below the eyes"),
                FMath::IsNearlyEqual(Player->PlayerCamera->GetComponentLocation().Z - Hand->GetComponentLocation().Z, 35.0, 0.01));

        UClass* EnemyClass = LoadClass<ANLEnemyCharacter>(nullptr,
            TEXT("/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_sword.BP_Level_sword_C"));
        if (!TestNotNull(TEXT("Current opening sword enemy asset"), EnemyClass)) return false;
        ANLEnemyCharacter* Enemy = Scope.World->SpawnActor<ANLEnemyCharacter>(EnemyClass, FVector(400, 0, 88), FRotator::ZeroRotator);
        if (!TestNotNull(TEXT("Actual main-level enemy"), Enemy)) return false;
        // Spawn collision raises the capsule slightly. Let the native movement
        // and grounded presentation place its visible feet on the test floor.
        Enemy->GetCharacterMovement()->TickComponent(1.0f / 60.0f, LEVELTICK_All, nullptr);
        Enemy->Tick(0.0f);
        Enemy->GetMesh()->TickAnimation(0.0f, false);
        Enemy->GetMesh()->RefreshBoneTransforms();
        const FVector EnemyEyes = Enemy->GetMesh()->GetSocketTransform(TEXT("head")).TransformPositionNoScale(Player->EnemyEyeOffset);
        AddInfo(FString::Printf(TEXT("Measured eye alignment: player=%.3f, enemy=%.3f, enemy actor Z=%.3f, mesh Z=%.3f, begun=%d"),
            Player->PlayerCamera->GetComponentLocation().Z, EnemyEyes.Z, Enemy->GetActorLocation().Z,
            Enemy->GetMesh()->GetComponentLocation().Z, Enemy->HasActorBegunPlay()));
        TestTrue(TEXT("Player eyes align within 1 cm of the actual opening enemy's neutral eyes on the same floor"),
            FMath::Abs(Player->PlayerCamera->GetComponentLocation().Z - EnemyEyes.Z) < 1.0);

        const float Calibration = Player->StandingTrackingHeightOffset;
        Player->HeadTrackingPosition.Z -= PhysicalCrouchDepth;
        Player->PlayerCamera->SetRelativeLocation(Player->HeadTrackingPosition);
        TestTrue(TEXT("A physical 45 cm crouch lowers the camera by 45 cm"),
            FMath::IsNearlyEqual(Player->PlayerCamera->GetComponentLocation().Z, ExpectedCrouchedEyeHeight, 0.1));
        Player->OnSpatialStateRestored();
        TestEqual(TEXT("Crouched retry retains the original standing calibration"), Player->StandingTrackingHeightOffset, Calibration);
        TestTrue(TEXT("Crouched retry does not raise the player's head back to standing"),
            FMath::IsNearlyEqual(Player->PlayerCamera->GetComponentLocation().Z, ExpectedCrouchedEyeHeight, 0.1));
        Player->HeadTrackingPosition.Z += PhysicalCrouchDepth;
        Player->PlayerCamera->SetRelativeLocation(Player->HeadTrackingPosition);
        const double EyeBeforeTurn = Player->PlayerCamera->GetComponentLocation().Z;
        Player->ApplySnapTurn(1.0f);
        TestTrue(TEXT("Snap turning preserves calibrated height"),
            FMath::IsNearlyEqual(Player->PlayerCamera->GetComponentLocation().Z, EyeBeforeTurn, 0.01));
        Player->HeadTrackingPosition.X += 20.0;
        Player->PlayerCamera->SetRelativeLocation(Player->HeadTrackingPosition);
        const FVector HeadBeforeRoomScale = Player->PlayerCamera->GetComponentLocation();
        Player->UpdateRoomScaleCapsule();
        TestTrue(TEXT("Room-scale capsule motion keeps the calibrated world view"),
            Player->PlayerCamera->GetComponentLocation().Equals(HeadBeforeRoomScale, 0.01));

        Player->UpdateTrackingState(0.0f); // The automation process runs with -nohmd.
        TestTrue(TEXT("Flat diagnostic fallback does not apply the height offset twice"),
            FMath::IsNearlyEqual(Player->PlayerCamera->GetComponentLocation().Z,
                Player->GetActorLocation().Z - Player->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() + ExpectedStandingEyeHeight, 0.01));
        TestEqual(TEXT("Tracking loss retains the standing calibration"), Player->StandingTrackingHeightOffset, Calibration);
        Player->bHMDTrackingActive = true;
        Player->PlayerCamera->SetRelativeLocationAndRotation(Player->HeadTrackingPosition, Player->HeadTrackingRotation);
        Player->RecenterFloorOrigin();
        TestTrue(TEXT("Reacquired tracking still uses the original eye height"),
            FMath::IsNearlyEqual(Player->PlayerCamera->GetComponentLocation().Z, ExpectedStandingEyeHeight, 0.1));
    }
    {
        FScopedWorld Scope(false);
        ANLVRPlayerCharacter* Player = Scope.Player;
        if (!TestNotNull(TEXT("Laboratory VR pawn"), Player)) return false;
        Player->bHMDTrackingActive = true;
        Player->HeadTrackingPosition = FVector(0, 0, 180);
        Player->PlayerCamera->SetRelativeLocation(Player->HeadTrackingPosition);
        Player->RecenterFloorOrigin();
        TestTrue(TEXT("A taller player also receives a signed correction"), Player->StandingTrackingHeightOffset < 0.0f);
        TestTrue(TEXT("The laboratory uses its own authored enemy eye height"),
            FMath::IsNearlyEqual(Player->PlayerCamera->GetComponentLocation().Z,
                static_cast<double>(Player->InitialEncounterEyeHeight), 0.01));
    }
    return true;
}

#endif
