// Syringe Pump Controller — Arduino Firmware
// Protocol: commands end with '\n', responses end with '\n'
//
// Commands:
//   ENERGIZE:<id>
//   DEENERGIZE:<id>
//   HOME:<id>
//   MOVE:<id>:<steps>:<steps_per_sec>
//   STOP:<id>
//   LIMIT:<id>:<aft|forward>
//
// Responses: "OK\n" or "1\n"/"0\n" for LIMIT queries.

#include <AccelStepper.h>

// TODO: Set these pin numbers after wiring is complete
#define PUMP1_STEP_PIN    2
#define PUMP1_DIR_PIN     3
#define PUMP1_ENABLE_PIN  4
#define PUMP1_AFT_PIN     5
#define PUMP1_FWD_PIN     6

#define PUMP2_STEP_PIN    7
#define PUMP2_DIR_PIN     8
#define PUMP2_ENABLE_PIN  9
#define PUMP2_AFT_PIN    10
#define PUMP2_FWD_PIN    11

#define PUMP3_STEP_PIN   12
#define PUMP3_DIR_PIN    13
#define PUMP3_ENABLE_PIN A0
#define PUMP3_AFT_PIN    A1
#define PUMP3_FWD_PIN    A2

// Normally-closed: LOW signal = switch activated (broken wire = fault detected)
#define LIMIT_NORMALLY_CLOSED true

AccelStepper steppers[3] = {
    AccelStepper(AccelStepper::DRIVER, PUMP1_STEP_PIN, PUMP1_DIR_PIN),
    AccelStepper(AccelStepper::DRIVER, PUMP2_STEP_PIN, PUMP2_DIR_PIN),
    AccelStepper(AccelStepper::DRIVER, PUMP3_STEP_PIN, PUMP3_DIR_PIN),
};

const int ENABLE_PINS[3] = {PUMP1_ENABLE_PIN, PUMP2_ENABLE_PIN, PUMP3_ENABLE_PIN};
const int AFT_PINS[3]    = {PUMP1_AFT_PIN,    PUMP2_AFT_PIN,    PUMP3_AFT_PIN};
const int FWD_PINS[3]    = {PUMP1_FWD_PIN,    PUMP2_FWD_PIN,    PUMP3_FWD_PIN};

bool readLimit(int idx, bool forward) {
    int pin  = forward ? FWD_PINS[idx] : AFT_PINS[idx];
    bool raw = (digitalRead(pin) == LOW);
    return LIMIT_NORMALLY_CLOSED ? raw : !raw;
}

void setup() {
    Serial.begin(115200);
    for (int i = 0; i < 3; i++) {
        pinMode(ENABLE_PINS[i], OUTPUT);
        digitalWrite(ENABLE_PINS[i], HIGH);   // disabled (active LOW)
        pinMode(AFT_PINS[i], INPUT_PULLUP);
        pinMode(FWD_PINS[i], INPUT_PULLUP);
        steppers[i].setMaxSpeed(10000);
        steppers[i].setAcceleration(1000);
    }
}

void loop() {
    for (int i = 0; i < 3; i++) steppers[i].run();

    if (!Serial.available()) return;

    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    int c1 = cmd.indexOf(':');
    String command = cmd.substring(0, c1);
    String rest    = cmd.substring(c1 + 1);
    int id  = rest.substring(0, rest.indexOf(':')).toInt();
    int idx = id - 1;

    if (idx < 0 || idx > 2) { Serial.println("ERR:bad_id"); return; }

    if (command == "ENERGIZE") {
        digitalWrite(ENABLE_PINS[idx], LOW);
        Serial.println("OK");

    } else if (command == "DEENERGIZE") {
        digitalWrite(ENABLE_PINS[idx], HIGH);
        Serial.println("OK");

    } else if (command == "STOP") {
        steppers[idx].stop();
        Serial.println("OK");

    } else if (command == "HOME") {
        steppers[idx].setSpeed(-200);   // slow aft movement
        steppers[idx].runSpeed();
        Serial.println("OK");

    } else if (command == "MOVE") {
        // MOVE:<id>:<steps>:<steps_per_sec>
        int c2   = rest.indexOf(':');
        int c3   = rest.indexOf(':', c2 + 1);
        long steps  = rest.substring(c2 + 1, c3).toInt();
        float speed = rest.substring(c3 + 1).toFloat();
        steppers[idx].setMaxSpeed(speed);
        steppers[idx].move(steps);
        Serial.println("OK");

    } else if (command == "LIMIT") {
        bool fwd = rest.endsWith("forward");
        Serial.println(readLimit(idx, fwd) ? "1" : "0");

    } else {
        Serial.println("ERR:unknown_cmd");
    }
}
