#include "AI/NLEnemyCharacter.h"

#include "AI/AIController.h"
#include "AI/NLEnemyBrainComponent.h"
#include "GameFramework/CharacterMovementComponent.h"

ANLEnemyCharacter::ANLEnemyCharacter()
{
	PrimaryActorTick.bCanEverTick = false;
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
	AIControllerClass = AAIController::StaticClass();

	EnemyBrain = CreateDefaultSubobject<UNLEnemyBrainComponent>(TEXT("EnemyBrain"));
	GetCharacterMovement()->bOrientRotationToMovement = true;
	GetCharacterMovement()->MaxWalkSpeed = 240.0f;
	bUseControllerRotationYaw = false;
}

void ANLEnemyCharacter::BeginPlay()
{
	Super::BeginPlay();
	if (EnemyBrain)
	{
		EnemyBrain->StartBrain();
	}
}
