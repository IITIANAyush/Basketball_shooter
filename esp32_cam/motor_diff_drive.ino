// Motor Driver 1 (base 4 motors)
#define ENA 5
#define IN1 2
#define IN2 3
#define ENB 6
#define IN3 4
#define IN4 7

// Motor Driver 2 (top motors)
#define ENA2 9
#define IN5 8
#define IN6 10
#define ENB2 11
#define IN7 12
#define IN8 13

// BO Motor
#define BO_MOTOR  A0

char cmd;
unsigned long lastCmdTime = 0;

// ===== SETUP =====
void setup() {
  Serial.begin(115200);

  pinMode(ENA, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(ENB, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  pinMode(ENA2, OUTPUT);
  pinMode(IN5, OUTPUT);
  pinMode(IN6, OUTPUT);
  pinMode(ENB2, OUTPUT);
  pinMode(IN7, OUTPUT);
  pinMode(IN8, OUTPUT);

  pinMode(BO_MOTOR, OUTPUT);
}

// ===== MOTOR FUNCTIONS =====
void forward() {
  analogWrite(ENA, 200);
  analogWrite(ENB, 200);

  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
}

void backward() {
  analogWrite(ENA, 200);
  analogWrite(ENB, 200);

  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
}

void left() {
  analogWrite(ENA, 150);
  analogWrite(ENB, 200);

  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
}

void right() {
  analogWrite(ENA, 200);
  analogWrite(ENB, 150);

  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
}

void stopMotors() {
  analogWrite(ENA, 0);
  analogWrite(ENB, 0);
}

// Top motors
void topMotors() {
  analogWrite(ENA2, 180);
  analogWrite(ENB2, 120);

  digitalWrite(IN5, HIGH);
  digitalWrite(IN6, LOW);
  digitalWrite(IN7, HIGH);
  digitalWrite(IN8, LOW);
}

// BO motor
void boMotorOn() {
  digitalWrite(BO_MOTOR, HIGH);
}

void boMotorOff() {
  digitalWrite(BO_MOTOR, LOW);
}

// ===== LOOP =====
void loop() {
  if (Serial.available()) {
    cmd = Serial.read();
    lastCmdTime = millis();

    switch (cmd) {
      case 'F': forward(); break;
      case 'B': backward(); break;
      case 'L': left(); break;
      case 'R': right(); break;
      case 'S': stopMotors(); break;
      case 'T': topMotors(); break;
      case 'O': boMotorOn(); break;
      case 'P': boMotorOff(); break;
    }
  }

  // FAILSAFE
  if (millis() - lastCmdTime > 500) {
    stopMotors();
  }
}
