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
#define PUMP3_DIR_PIN    A3   // Fix 6: was 13 (built-in LED), changed to A3
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

// Fix 2: homing state array — true while a stepper is seeking the aft limit
bool homing[3] = {false, false, false};

bool readLimit(int idx, bool forward) {
    int pin  = forward ? FWD_PINS[idx] : AFT_PINS[idx];
    bool raw = (digitalRead(pin) == LOW);
    return LIMIT_NORMALLY_CLOSED ? raw : !raw;
}

void setup() {
    Serial.begin(115200);
    Serial.setTimeout(20);   // Fix 1: 20 ms keeps readBytesUntil from stalling steppers
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
    // Fix 2: drive each stepper with the appropriate motion mode
    for (int i = 0; i < 3; i++) {
        if (homing[i]) {
            if (readLimit(i, false)) {   // aft limit hit → immediate halt
                // setCurrentPosition zeroes the target in-place for an instant stop,
                // avoiding the deceleration overshoot that stop() would produce.
                steppers[i].setCurrentPosition(steppers[i].currentPosition());
                homing[i] = false;
            } else {
                steppers[i].runSpeed();  // continue constant-speed aft motion
            }
        } else {
            steppers[i].run();           // normal position-based motion
        }
    }

    if (!Serial.available()) return;

    // Fix 3: fixed char buffer instead of String — avoids heap fragmentation
    char buf[64];
    int len = Serial.readBytesUntil('\n', buf, sizeof(buf) - 1);
    if (len == 0) return;
    buf[len] = '\0';
    // strip trailing '\r' if present
    if (len > 0 && buf[len-1] == '\r') buf[--len] = '\0';

    char *tok = strtok(buf, ":");
    if (!tok) return;
    char command[20];
    strncpy(command, tok, sizeof(command) - 1);
    command[sizeof(command)-1] = '\0';

    tok = strtok(NULL, ":");
    if (!tok) { Serial.println("ERR:bad_format"); return; }
    int id  = atoi(tok);
    int idx = id - 1;

    if (idx < 0 || idx > 2) { Serial.println("ERR:bad_id"); return; }

    if (strcmp(command, "ENERGIZE") == 0) {
        digitalWrite(ENABLE_PINS[idx], LOW);
        Serial.println("OK");

    } else if (strcmp(command, "DEENERGIZE") == 0) {
        digitalWrite(ENABLE_PINS[idx], HIGH);
        Serial.println("OK");

    // Fix 4: STOP decelerates using AccelStepper's configured acceleration profile.
    // This is intentional for mechanical safety — syringe plungers should not hard-stop.
    } else if (strcmp(command, "STOP") == 0) {
        homing[idx] = false;   // Fix 2: cancel any in-progress homing
        steppers[idx].stop();
        Serial.println("OK");

    } else if (strcmp(command, "HOME") == 0) {
        steppers[idx].setSpeed(-200);   // slow aft movement
        homing[idx] = true;             // Fix 2: let loop() drive the motion
        Serial.println("OK");

    } else if (strcmp(command, "MOVE") == 0) {
        tok = strtok(NULL, ":");
        if (!tok) { Serial.println("ERR:bad_format"); return; }
        long steps = atol(tok);
        tok = strtok(NULL, ":");
        if (!tok) { Serial.println("ERR:bad_format"); return; }
        float speed = atof(tok);
        // Fix 5: Safety — refuse move if already at the limit in the commanded direction
        if (steps > 0 && readLimit(idx, true)) {
            Serial.println("ERR:at_fwd_limit");
            return;
        }
        if (steps < 0 && readLimit(idx, false)) {
            Serial.println("ERR:at_aft_limit");
            return;
        }
        homing[idx] = false;
        steppers[idx].setMaxSpeed(speed);
        steppers[idx].move(steps);
        Serial.println("OK");

    } else if (strcmp(command, "LIMIT") == 0) {
        tok = strtok(NULL, ":");
        bool fwd = (tok && strcmp(tok, "forward") == 0);
        Serial.println(readLimit(idx, fwd) ? "1" : "0");

    } else {
        Serial.println("ERR:unknown_cmd");
    }
}
