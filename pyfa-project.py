"""Factory I/O color sorting process.

Run this file with:
    python pyfa-project.py

Factory I/O must be in RUN mode and the Modbus TCP/IP Server driver must be connected.
Press Ctrl+C to stop all outputs safely.
"""

# Cell 1: Modbus connection
from pymodbus.client import ModbusTcpClient
import csv
import os
import time as tt
import threading

IP_ADDRESS = '210.119.14.76'
PORT = 502
UNIT_ID = 1

client = ModbusTcpClient(IP_ADDRESS, port=PORT)
connected = False

# Cell 2: I/O mapping from Factory I/O driver
# Updated for the current Factory I/O driver screen.
# Input Reg 0 = Vision Sensor 0 Value, configured to detect product colors.
IN_VISION_SENSOR_0 = 0
IN_BLUE_SENSOR = IN_VISION_SENSOR_0
IN_MC0_OPENED = 1
IN_MC0_BUSY = 2
IN_MC0_ERROR = 3
IN_PUSHER_FRONT = 4
IN_PUSHER_BACK = 5
IN_MC1_OPENED = 6
IN_MC1_BUSY = 7
IN_MC1_ERROR = 8
IN_SENSOR_1 = 9
IN_SENSOR_2 = 10
IN_SENSOR_3 = 11
IN_SENSOR_4 = 12
IN_SENSOR_0 = 13
IN_SENSOR_5 = 14

REG_VISION_SENSOR_0_VALUE = 0
REG_MC0_PROGRESS = 1
REG_MC1_PROGRESS = 2

COIL_EMITTER_0 = 0
COIL_MC0_STOP = 1
COIL_MC0_RESET = 2
COIL_MC0_START = 3
COIL_MC0_PRODUCE = 4
COIL_PUSHER_0 = 5
COIL_REMOVER_0 = 6
COIL_REMOVER_1 = 7
COIL_EMITTER_1 = 9
COIL_MC1_STOP = 10
COIL_MC1_RESET = 11
COIL_MC1_START = 12
COIL_MC1_PRODUCE = 13
COIL_BELT_2M_0 = 14
COIL_BELT_2M_2 = 15
COIL_BELT_4M_0 = 16
COIL_BELT_4M_1 = 17
COIL_BELT_4M_2 = 18
COIL_BELT_6M_0 = 19
COIL_BELT_6M_1 = 20
COIL_BELT_6M_2 = 21
COIL_BELT_6M_3 = 22
COIL_CURVE_0_CW = 23
COIL_CURVE_3_CW = 24
COIL_CURVE_1_CCW = 25
COIL_CURVE_2_CCW = 26
COIL_CURVE_4_CCW = 27
COIL_BELT_4M_3 = 28

# Cell 3: process settings
CONVEYOR_COILS = [
    COIL_BELT_2M_0,
    COIL_BELT_2M_2,
    COIL_BELT_4M_0,
    COIL_BELT_4M_1,
    COIL_BELT_4M_2,
    COIL_BELT_4M_3,
    COIL_BELT_6M_0,
    COIL_BELT_6M_1,
    COIL_BELT_6M_2,
    COIL_BELT_6M_3,
    COIL_CURVE_0_CW,
    COIL_CURVE_3_CW,
    COIL_CURVE_1_CCW,
    COIL_CURVE_2_CCW,
    COIL_CURVE_4_CCW,
]

# Vision Sensor 0 Value must be mapped to Input Reg 0 in Factory I/O.
# Common values in this scene: 1 = blue, 4 = green, 0 = no product.
VISION_VALUE_REGISTER = REG_VISION_SENSOR_0_VALUE
VISION_BLUE_VALUE = 1
VISION_GREEN_VALUE = 4
EXIT_SENSOR = IN_SENSOR_4
# Retroreflective Sensor 0 counts blue materials, Sensor 5 counts green materials.
BLUE_COUNT_SENSOR = IN_SENSOR_0
GREEN_COUNT_SENSOR = IN_SENSOR_5
COUNT_STARTUP_IGNORE_TIME = 2.0
COLOR_COUNT_COOLDOWN = 1.0

VISION_SENSOR_DEBUG = True
MODBUS_RECORD_ENABLED = True
MODBUS_RECORD_FILE = 'modbus_records.csv'
MODBUS_RECORD_RESET_ON_START = True
MODBUS_SNAPSHOT_INTERVAL = 0.20
MODBUS_RECORD_EVENTS = {
    'count_started',
    'blue_counted',
    'green_counted',
}

# Vision Sensor 0 alone decides sorting.
# Input Reg 0 == 1 -> blue -> pusher ON.
# Input Reg 0 == 4 -> green -> pusher OFF and pass.

EMIT_TIME = 0.35
START_HOLD = 0.5
PRODUCE_HOLD = 10.0
WAIT_BUSY_TIMEOUT = 12.0

FEED_TO_MC0_TIME = 4.5
FEED_TO_MC1_TIME = 5.5
MACHINE_TIMEOUT = 20.0
WAIT_SORT_DONE_TIMEOUT = 35.0
REPEAT_DELAY = 0.8

MC0_PRODUCT_NAME = 'blue material/processed product line'
MC1_PRODUCT_NAME = 'green material/processed product line'

SENSOR_CONFIRM_TIME = 0.00

# Keep this at 0.00 to push immediately when Vision Sensor detects blue.
BLUE_TO_PUSHER_DELAY = 0.50
PUSH_TIME = 3.00
PUSH_EXTEND_TIMEOUT = 1.50
PUSH_RETRACT_TIMEOUT = 1.00
PUSH_COOLDOWN = 0.50

STOP_CONVEYORS_DURING_MACHINING = False
POST_MACHINE_RELEASE_TIME = 0.8
START_RETRY_COUNT = 3
START_RETRY_PULSE = 0.3

REMOVE_TIME = 0.45
SCAN_TIME = 0.005

process_run = False
machine_repeat_run = False

production_thread = None
sorting_thread = None
machine_repeat_thread = None
blue_push_thread = None
modbus_record_thread = None
blue_push_busy = False
blue_sensor_latched = False
blue_push_pending = 0
blue_material_count = 0
green_material_count = 0
last_blue_counted_at = 0.0
last_green_counted_at = 0.0
blue_push_lock = threading.Lock()
sort_done_event = threading.Event()
exit_event = threading.Event()
machining_lock = threading.Lock()
active_machining_count = 0
modbus_record_lock = threading.Lock()
logged_coil_values = {}
current_modbus_record_file = MODBUS_RECORD_FILE
modbus_record_file_started_at = 0.0

MODBUS_RECORD_HEADER = ['datetime', 'blue', 'green']

COIL_NAMES = {
    COIL_EMITTER_0: 'Emitter 0',
    COIL_MC0_STOP: 'MC0 Stop',
    COIL_MC0_RESET: 'MC0 Reset',
    COIL_MC0_START: 'MC0 Start',
    COIL_MC0_PRODUCE: 'MC0 Produce Lids',
    COIL_PUSHER_0: 'Pusher 0',
    COIL_REMOVER_0: 'Remover 0',
    COIL_REMOVER_1: 'Remover 1',
    COIL_EMITTER_1: 'Emitter 1',
    COIL_MC1_STOP: 'MC1 Stop',
    COIL_MC1_RESET: 'MC1 Reset',
    COIL_MC1_START: 'MC1 Start',
    COIL_MC1_PRODUCE: 'MC1 Produce Lids',
}

REGISTER_NAMES = {
    REG_VISION_SENSOR_0_VALUE: 'Vision Sensor 0 Value',
    REG_MC0_PROGRESS: 'MC0 Progress',
    REG_MC1_PROGRESS: 'MC1 Progress',
}

# Cell 4: Modbus helper functions
def _is_error(result):
    return hasattr(result, 'isError') and result.isError()

def make_modbus_record_filename(start_time=None):
    if start_time is None:
        start_time = tt.time()

    base, ext = os.path.splitext(MODBUS_RECORD_FILE)
    if not ext:
        ext = '.csv'

    timestamp = tt.strftime('%Y%m%d_%H%M%S', tt.localtime(start_time))
    return f'{base}_{timestamp}{ext}'

def write_modbus_record_header(file_path):
    with open(file_path, 'w', newline='', encoding='utf-8') as log_file:
        writer = csv.writer(log_file)
        writer.writerow(MODBUS_RECORD_HEADER)

def ensure_modbus_record_file_exists(now=None):
    global current_modbus_record_file, modbus_record_file_started_at

    if now is None:
        now = tt.time()

    if modbus_record_file_started_at <= 0:
        modbus_record_file_started_at = now
        current_modbus_record_file = make_modbus_record_filename(now)
        write_modbus_record_header(current_modbus_record_file)
        return

def init_modbus_record_file(reset_file=MODBUS_RECORD_RESET_ON_START):
    global current_modbus_record_file, modbus_record_file_started_at

    if not MODBUS_RECORD_ENABLED:
        return

    with modbus_record_lock:
        if reset_file or modbus_record_file_started_at <= 0:
            modbus_record_file_started_at = tt.time()
            current_modbus_record_file = make_modbus_record_filename(modbus_record_file_started_at)
            write_modbus_record_header(current_modbus_record_file)
        elif not os.path.exists(current_modbus_record_file) or os.path.getsize(current_modbus_record_file) == 0:
            write_modbus_record_header(current_modbus_record_file)

def log_modbus_record(event, area='', addr='', value='', detail=''):
    if not MODBUS_RECORD_ENABLED:
        return

    if event not in MODBUS_RECORD_EVENTS:
        return

    timestamp = tt.strftime('%Y-%m-%d %H:%M:%S')
    row = [timestamp, f'blue={blue_material_count}', f'green={green_material_count}']

    with modbus_record_lock:
        ensure_modbus_record_file_exists()
        need_header = not os.path.exists(current_modbus_record_file) or os.path.getsize(current_modbus_record_file) == 0

        with open(current_modbus_record_file, 'a', newline='', encoding='utf-8') as log_file:
            writer = csv.writer(log_file)

            if need_header:
                writer.writerow(MODBUS_RECORD_HEADER)

            writer.writerow(row)

def read_input(addr):
    try:
        result = client.read_discrete_inputs(addr, count=1, slave=UNIT_ID)
    except TypeError:
        result = client.read_discrete_inputs(addr, count=1)
    if _is_error(result):
        raise RuntimeError(f'Input {addr} read failed')
    return bool(result.bits[0])

def read_register(addr):
    try:
        result = client.read_input_registers(addr, count=1, slave=UNIT_ID)
    except TypeError:
        result = client.read_input_registers(addr, count=1)
    if _is_error(result):
        raise RuntimeError(f'Input register {addr} read failed')
    return result.registers[0]

def read_holding_register(addr):
    try:
        result = client.read_holding_registers(addr, count=1, slave=UNIT_ID)
    except TypeError:
        result = client.read_holding_registers(addr, count=1)
    if _is_error(result):
        raise RuntimeError(f'Holding register {addr} read failed')
    return result.registers[0]

def write_coil(addr, value):
    value = bool(value)

    try:
        result = client.write_coil(addr, value, slave=UNIT_ID)
    except TypeError:
        result = client.write_coil(addr, value)
    if _is_error(result):
        raise RuntimeError(f'Coil {addr} write failed')

    if addr not in CONVEYOR_COILS and logged_coil_values.get(addr) != value:
        logged_coil_values[addr] = value
        log_modbus_record(
            'write_coil',
            'coil',
            addr,
            int(value),
            COIL_NAMES.get(addr, ''),
        )

    return result

def write_coils(addr, values):
    try:
        result = client.write_coils(addr, values, slave=UNIT_ID)
    except TypeError:
        result = client.write_coils(addr, values)
    if _is_error(result):
        raise RuntimeError(f'Coils from {addr} write failed')

    log_modbus_record('write_coils', 'coil', addr, list(map(int, values)), f'count={len(values)}')

    return result

def write_register(addr, value):
    value = int(value)

    try:
        result = client.write_register(addr, value, slave=UNIT_ID)
    except TypeError:
        result = client.write_register(addr, value)
    if _is_error(result):
        raise RuntimeError(f'Holding register {addr} write failed')

    log_modbus_record(
        'write_register',
        'holding_register',
        addr,
        value,
        REGISTER_NAMES.get(addr, ''),
    )

    return result

def write_registers(addr, values):
    values = [int(v) for v in values]
    try:
        result = client.write_registers(addr, values, slave=UNIT_ID)
    except TypeError:
        result = client.write_registers(addr, values)
    if _is_error(result):
        raise RuntimeError(f'Holding registers from {addr} write failed')

    log_modbus_record('write_registers', 'holding_register', addr, values, f'count={len(values)}')

    return result

def read_modbus_snapshot():
    vision_value = read_register(VISION_VALUE_REGISTER)

    return {
        'vision_value': vision_value,
        'blue_detected': vision_value == VISION_BLUE_VALUE,
        'blue_count': blue_material_count,
        'green_count': green_material_count,
        'pusher_busy': blue_push_busy,
    }

def count_blue_from_vision():
    global blue_material_count, last_blue_counted_at

    now = tt.time()
    if now - last_blue_counted_at < COLOR_COUNT_COOLDOWN:
        return

    blue_material_count += 1
    last_blue_counted_at = now
    print('Blue material count =', blue_material_count)
    log_modbus_record('blue_counted', 'input_register', VISION_VALUE_REGISTER, blue_material_count, 'Vision Sensor 0 blue')

def count_green_from_vision():
    global green_material_count, last_green_counted_at

    now = tt.time()
    if now - last_green_counted_at < COLOR_COUNT_COOLDOWN:
        return

    green_material_count += 1
    last_green_counted_at = now
    print('Green material count =', green_material_count)
    log_modbus_record('green_counted', 'input_register', VISION_VALUE_REGISTER, green_material_count, 'Vision Sensor 0 green')

def update_material_counts(
    prev_blue_sensor,
    prev_green_sensor,
    blue_idle_state,
    green_idle_state,
    blue_count_armed,
    green_count_armed,
):
    global blue_material_count, green_material_count

    blue_sensor = read_input(BLUE_COUNT_SENSOR)
    green_sensor = read_input(GREEN_COUNT_SENSOR)

    blue_detected = blue_sensor != blue_idle_state
    prev_blue_detected = prev_blue_sensor != blue_idle_state
    green_detected = green_sensor != green_idle_state
    prev_green_detected = prev_green_sensor != green_idle_state

    if not blue_detected:
        blue_count_armed = True

    if not green_detected:
        green_count_armed = True

    if blue_detected and not prev_blue_detected and blue_count_armed:
        blue_material_count += 1
        blue_count_armed = False
        print('Blue material count =', blue_material_count)
        log_modbus_record('blue_counted', 'input', BLUE_COUNT_SENSOR, blue_material_count, 'Retroreflective Sensor 0')

    if green_detected and not prev_green_detected and green_count_armed:
        green_material_count += 1
        green_count_armed = False
        print('Green material count =', green_material_count)
        log_modbus_record('green_counted', 'input', GREEN_COUNT_SENSOR, green_material_count, 'Retroreflective Sensor 5')

    return blue_sensor, green_sensor, blue_count_armed, green_count_armed

def modbus_record_loop():
    print('Modbus record loop started:', current_modbus_record_file)
    prev_snapshot = None

    while process_run:
        try:
            snapshot = read_modbus_snapshot()

            if snapshot != prev_snapshot:
                log_modbus_record('state_change', 'modbus', '', snapshot, 'changed state')
                prev_snapshot = snapshot
        except Exception as exc:
            log_modbus_record('snapshot_error', detail=str(exc))

        tt.sleep(MODBUS_SNAPSHOT_INTERVAL)

    log_modbus_record('record_loop_stop', detail='Modbus record loop stopped')

def pulse_coil(addr, seconds=0.5):
    write_coil(addr, True)
    tt.sleep(seconds)
    write_coil(addr, False)

# Cell 5: stop and conveyor functions
def conveyors_on():
    for coil in CONVEYOR_COILS:
        write_coil(coil, True)

def conveyors_off():
    for coil in CONVEYOR_COILS:
        write_coil(coil, False)

def stop_all():
    global process_run, machine_repeat_run, connected
    process_run = False
    machine_repeat_run = False
    try:
        if connected:
            write_coils(0, [False] * 30)
        else:
            print('Modbus is not connected; skipped writing stop coils')
    except Exception as exc:
        connected = False
        print('Stop outputs skipped because Modbus is unavailable:', exc)

    log_modbus_record('process_stop', detail='Stop requested')
    print('All local process flags stopped')

# Cell 6: machining center and actuator functions
MACHINES = {
    'mc0': {
        'color': 'blue',
        'stop': COIL_MC0_STOP,
        'reset': COIL_MC0_RESET,
        'start': COIL_MC0_START,
        'produce': COIL_MC0_PRODUCE,
        'busy': IN_MC0_BUSY,
        'error': IN_MC0_ERROR,
        'progress': REG_MC0_PROGRESS,
        'feed_time': FEED_TO_MC0_TIME,
        'product_name': MC0_PRODUCT_NAME,
    },
    'mc1': {
        'color': 'green',
        'stop': COIL_MC1_STOP,
        'reset': COIL_MC1_RESET,
        'start': COIL_MC1_START,
        'produce': COIL_MC1_PRODUCE,
        'busy': IN_MC1_BUSY,
        'error': IN_MC1_ERROR,
        'progress': REG_MC1_PROGRESS,
        'feed_time': FEED_TO_MC1_TIME,
        'product_name': MC1_PRODUCT_NAME,
    },
}

def machine_status(name):
    m = MACHINES[name]
    return {
        'busy': read_input(m['busy']),
        'error': read_input(m['error']),
        'progress': read_register(m['progress']),
    }

def reset_machine(name):
    m = MACHINES[name]
    write_coil(m['stop'], False)
    write_coil(m['start'], False)
    write_coil(m['produce'], False)
    pulse_coil(m['reset'], 0.7)
    tt.sleep(0.3)
    write_coil(m['reset'], False)
    write_coil(m['stop'], False)

def reset_machines():
    reset_machine('mc0')
    reset_machine('mc1')

def enable_machine(name):
    m = MACHINES[name]
    write_coil(m['stop'], False)
    write_coil(m['reset'], False)
    write_coil(m['start'], True)
    tt.sleep(START_HOLD)

def pulse_machine_start(name):
    m = MACHINES[name]
    write_coil(m['start'], False)
    tt.sleep(0.1)
    write_coil(m['start'], True)
    tt.sleep(START_RETRY_PULSE)

def retry_machine_start(name, start_progress):
    for attempt in range(1, START_RETRY_COUNT + 1):
        print(name, 'retry start pulse', attempt)
        pulse_machine_start(name)
        if wait_until_busy_or_progress(name, start_progress, 1.5):
            return True
    return False

def disable_machine(name):
    m = MACHINES[name]
    write_coil(m['produce'], False)
    write_coil(m['start'], False)

def wait_until_busy_or_progress(name, start_progress, timeout):
    m = MACHINES[name]
    end_time = tt.time() + timeout

    while tt.time() < end_time:
        busy = read_input(m['busy'])
        progress = read_register(m['progress'])

        if busy or progress != start_progress:
            print(name, 'machining started busy=', busy, 'progress=', progress)
            return True

        tt.sleep(0.05)

    print(name, 'did not start busy/progress, progress=', read_register(m['progress']))
    return False

def wait_machine_done(name, start_progress=None, timeout=MACHINE_TIMEOUT):
    m = MACHINES[name]
    end_time = tt.time() + timeout
    saw_busy = False
    saw_progress_change = False

    while tt.time() < end_time:
        busy = read_input(m['busy'])
        progress = read_register(m['progress'])

        if busy:
            saw_busy = True

        if start_progress is None or progress != start_progress:
            saw_progress_change = True

        if saw_busy and not busy:
            print(name, 'machining finished, progress=', progress)
            return True

        if saw_progress_change and progress >= 100:
            print(name, 'progress reached 100')
            return True

        tt.sleep(0.1)

    print(name, 'finish wait timeout busy=', read_input(m['busy']), 'progress=', read_register(m['progress']))
    return saw_busy or saw_progress_change

def begin_machining_hold(name):
    global active_machining_count

    with machining_lock:
        active_machining_count += 1

    conveyors_on()
    print(name, 'machining active: conveyors stay ON')

def end_machining_hold(name):
    global active_machining_count

    with machining_lock:
        active_machining_count = max(0, active_machining_count - 1)

    conveyors_on()
    print(name, 'machining finished: conveyors stay ON')

def hold_product_until_machining_done(name, start_progress=None):
    begin_machining_hold(name)

    try:
        return wait_machine_done(name, start_progress=start_progress, timeout=MACHINE_TIMEOUT)
    finally:
        end_machining_hold(name)

def run_machine(name):
    m = MACHINES[name]

    if read_input(m['error']):
        print(name, 'has error, resetting')
        reset_machine(name)

    enable_machine(name)

    start_progress = read_register(m['progress'])
    write_coil(m['produce'], True)
    print(name, 'START ON, PRODUCE LIDS ON')

    started = wait_until_busy_or_progress(name, start_progress, WAIT_BUSY_TIMEOUT)

    if not started:
        print(name, 'holding Produce Lids and retrying Start')
        started = retry_machine_start(name, start_progress)

    if not started:
        started = wait_until_busy_or_progress(name, start_progress, PRODUCE_HOLD)

    if started:
        hold_product_until_machining_done(name, start_progress=start_progress)

    write_coil(m['produce'], False)

    status = machine_status(name)
    print(name, 'done', status)
    return started

def emit_mc0_blue():
    pulse_coil(COIL_EMITTER_0, EMIT_TIME)

def emit_mc1_green():
    pulse_coil(COIL_EMITTER_1, EMIT_TIME)

def feed_machine_and_run(name, emit_func):
    m = MACHINES[name]

    conveyors_on()
    reset_machine(name)
    enable_machine(name)

    if read_input(m['error']):
        print(name, 'has error after reset')
        return m['color']

    start_progress = read_register(m['progress'])
    write_coil(m['produce'], True)
    print(name, m['product_name'], 'ready before emit: START ON, PRODUCE LIDS ON')

    emit_func()
    print(name, m['product_name'], 'material emitted, waiting until machine captures it')

    started = wait_until_busy_or_progress(
        name,
        start_progress,
        m['feed_time'] + WAIT_BUSY_TIMEOUT,
    )

    if not started:
        print(name, 'machine did not capture yet, retrying Start while Produce Lids stays ON')
        started = retry_machine_start(name, start_progress)

    if not started:
        started = wait_until_busy_or_progress(name, start_progress, PRODUCE_HOLD)

    if started:
        hold_product_until_machining_done(name, start_progress=start_progress)
    else:
        print(name, 'material may have missed the machining position')
        print(name, 'adjust feed_time or check machine placement/driver mapping')
        conveyors_on()

    write_coil(m['produce'], False)

    status = machine_status(name)
    print(name, m['product_name'], 'cycle end', status)
    return m['color']

def feed_mc0_and_run():
    return feed_machine_and_run('mc0', emit_mc0_blue)

def feed_mc1_and_run():
    return feed_machine_and_run('mc1', emit_mc1_green)

def wait_for_input(addr, expected=True, timeout=2.0):
    end_time = tt.time() + timeout

    while tt.time() < end_time:
        if read_input(addr) == expected:
            return True

        tt.sleep(0.02)

    return False

def finish_pusher_cycle():
    reached_front = wait_for_input(IN_PUSHER_FRONT, True, PUSH_EXTEND_TIMEOUT)

    if not reached_front:
        tt.sleep(PUSH_TIME)

    write_coil(COIL_PUSHER_0, False)
    wait_for_input(IN_PUSHER_BACK, True, PUSH_RETRACT_TIMEOUT)
    print('Pusher cycle done')

def push_blue_product():
    if BLUE_TO_PUSHER_DELAY > 0:
        tt.sleep(BLUE_TO_PUSHER_DELAY)

    print('Pusher ON immediately: blue material')
    write_coil(COIL_PUSHER_0, True)
    finish_pusher_cycle()

def remove_unknown_product():
    print('Remover ON: unknown material only')
    pulse_coil(COIL_REMOVER_0, REMOVE_TIME)

def handle_sorting(color):
    if color == 'blue':
        push_blue_product()
    elif color == 'green':
        print('Green passed: pusher stays OFF')
        write_coil(COIL_PUSHER_0, False)
    else:
        write_coil(COIL_PUSHER_0, False)
        remove_unknown_product()

# Cell 7: full process - MC0/MC1 together, Vision Sensor blue pusher
# MC0 = blue material and processed product line.
# MC1 = green material and processed product line.
# MC0 and MC1 run at the same time.
# Vision Sensor 0 is the final color decision:
#   Input Reg 0 == 1 -> blue material/processed product -> Pusher 0 Coil 5 ON
#   Input Reg 0 != 1 -> non-blue product -> Pusher 0 OFF and pass


def read_vision_sensor_raw():
    return read_register(VISION_VALUE_REGISTER)


def is_blue_detected():
    return read_vision_sensor_raw() == VISION_BLUE_VALUE


def wait_stable_blue_sensor(seconds=SENSOR_CONFIRM_TIME):
    if seconds <= 0:
        return is_blue_detected()

    end_time = tt.time() + seconds
    while tt.time() < end_time:
        if not is_blue_detected():
            return False
        tt.sleep(SCAN_TIME)

    return True


def print_vision_sensor_state(raw_value):
    blue_detected = raw_value == VISION_BLUE_VALUE
    green_detected = raw_value == VISION_GREEN_VALUE

    if VISION_SENSOR_DEBUG:
        print(
            'Vision Sensor 0 value =', raw_value,
            'blue_value =', VISION_BLUE_VALUE,
            'green_value =', VISION_GREEN_VALUE,
            'blue_detected =', blue_detected,
            'green_detected =', green_detected,
        )

    log_modbus_record(
        'vision_sensor_change',
        'input_register',
        VISION_VALUE_REGISTER,
        raw_value,
        f'blue_detected={blue_detected}, green_detected={green_detected}',
    )


def machine_job(name):
    if name == 'mc0':
        log_modbus_record('machine_start', detail='mc0 blue material/processed product')
        print('Starting MC0:', MC0_PRODUCT_NAME)
        feed_mc0_and_run()
        log_modbus_record('machine_done', detail='mc0 blue material/processed product')
        print('MC0 blue material/processed product released')
    elif name == 'mc1':
        log_modbus_record('machine_start', detail='mc1 green material/processed product')
        print('Starting MC1:', MC1_PRODUCT_NAME)
        feed_mc1_and_run()
        log_modbus_record('machine_done', detail='mc1 green material/processed product')
        print('MC1 green material/processed product released: pusher OFF')


def wait_until_machines_done(threads, timeout=WAIT_SORT_DONE_TIMEOUT):
    end_time = tt.time() + timeout

    for th in threads:
        remaining = max(0.0, end_time - tt.time())
        th.join(remaining)

    done = all(not th.is_alive() for th in threads)

    if done:
        print('Both machining centers finished')
    else:
        print('Machine wait timeout')

    return done


def run_both_machines_once():
    log_modbus_record('cycle_start', detail='MC0 blue and MC1 green run together')
    print('Cycle start: MC0 blue and MC1 green material/processed product run together')
    conveyors_on()

    blue_thread = threading.Thread(target=machine_job, args=('mc0',), daemon=True)
    green_thread = threading.Thread(target=machine_job, args=('mc1',), daemon=True)

    blue_thread.start()
    green_thread.start()

    wait_until_machines_done([blue_thread, green_thread])
    tt.sleep(REPEAT_DELAY)


def production_loop():
    print('Production loop started: both machining centers run together repeatedly')

    while process_run:
        conveyors_on()
        run_both_machines_once()


def pulse_pusher_for_blue():
    log_modbus_record('pusher_cycle_start', 'coil', COIL_PUSHER_0, 1, 'Pusher 0')
    print('Vision Sensor 0 BLUE -> Coil 5 Pusher 0 ON immediately for', PUSH_TIME, 'seconds')
    write_coil(COIL_PUSHER_0, True)

    start_time = tt.time()
    while process_run and tt.time() - start_time < PUSH_TIME:
        conveyors_on()
        write_coil(COIL_PUSHER_0, True)
        tt.sleep(SCAN_TIME)

    print('Coil 5 Pusher 0 OFF')
    write_coil(COIL_PUSHER_0, False)
    wait_for_input(IN_PUSHER_BACK, True, PUSH_RETRACT_TIMEOUT)
    log_modbus_record('pusher_cycle_done', 'coil', COIL_PUSHER_0, 0, 'Pusher 0')
    print('Blue product pushed to branch conveyor')


def delayed_blue_push_from_vision():
    global blue_push_busy, blue_push_pending

    while process_run:
        with blue_push_lock:
            if blue_push_pending <= 0:
                blue_push_busy = False
                break

            blue_push_pending -= 1

        try:
            conveyors_on()

            if BLUE_TO_PUSHER_DELAY > 0:
                print('Blue detected: waiting', BLUE_TO_PUSHER_DELAY, 'seconds for pusher timing')
                start_time = tt.time()
                while process_run and tt.time() - start_time < BLUE_TO_PUSHER_DELAY:
                    conveyors_on()
                    write_coil(COIL_PUSHER_0, False)
                    tt.sleep(SCAN_TIME)

            if process_run:
                pulse_pusher_for_blue()
                sort_done_event.set()
                tt.sleep(PUSH_COOLDOWN)

        finally:
            write_coil(COIL_PUSHER_0, False)


def schedule_blue_push_from_vision():
    global blue_push_thread, blue_push_busy, blue_push_pending

    with blue_push_lock:
        blue_push_pending += 1

        if blue_push_busy:
            print('Vision Sensor 0 detected BLUE: queued Pusher 0 cycle, pending =', blue_push_pending)
            log_modbus_record('pusher_queued', 'coil', COIL_PUSHER_0, blue_push_pending, 'Pusher 0 pending cycles')
            return

        blue_push_busy = True

    print('Vision Sensor 0 detected BLUE: scheduling Pusher 0')
    log_modbus_record('pusher_scheduled', 'coil', COIL_PUSHER_0, 1, 'Pusher 0')
    blue_push_thread = threading.Thread(target=delayed_blue_push_from_vision, daemon=True)
    blue_push_thread.start()


def sorting_loop():
    global blue_sensor_latched

    prev_exit = False
    prev_raw = None
    blue_sensor_latched = False
    green_sensor_latched = False

    write_coil(COIL_PUSHER_0, False)
    print('Sorting loop started: blue -> Pusher 0, green -> pass')
    print('Material counts use Vision Sensor 0 color latches')

    while process_run:
        conveyors_on()

        raw_blue = read_vision_sensor_raw()
        blue_now = raw_blue == VISION_BLUE_VALUE
        green_now = raw_blue == VISION_GREEN_VALUE
        exit_sensor = read_input(EXIT_SENSOR)

        if raw_blue != prev_raw:
            print_vision_sensor_state(raw_blue)
            prev_raw = raw_blue

        if blue_now:
            green_sensor_latched = False

            if not blue_sensor_latched:
                blue_sensor_latched = True
                count_blue_from_vision()
                schedule_blue_push_from_vision()
        elif green_now:
            blue_sensor_latched = False

            if not green_sensor_latched:
                green_sensor_latched = True
                count_green_from_vision()
                print('Vision Sensor 0 detected GREEN: pusher OFF, product passes')
                log_modbus_record('green_passed', 'input_register', VISION_VALUE_REGISTER, raw_blue, 'Pusher 0 OFF')

            if not blue_push_busy:
                write_coil(COIL_PUSHER_0, False)
        else:
            blue_sensor_latched = False
            green_sensor_latched = False

        if exit_sensor and not prev_exit:
            print('Product reached exit')
            log_modbus_record('product_exit', 'input', EXIT_SENSOR, 1, 'Exit sensor')
            exit_event.set()

        if not blue_push_busy:
            write_coil(COIL_PUSHER_0, False)

        prev_exit = exit_sensor
        tt.sleep(SCAN_TIME)


def factory_process():
    global process_run, production_thread, sorting_thread, modbus_record_thread
    global blue_push_busy, blue_sensor_latched, blue_push_pending, active_machining_count
    global blue_material_count, green_material_count
    global last_blue_counted_at, last_green_counted_at

    process_run = True
    blue_push_busy = False
    blue_sensor_latched = False
    blue_push_pending = 0
    blue_material_count = 0
    green_material_count = 0
    last_blue_counted_at = 0.0
    last_green_counted_at = 0.0
    active_machining_count = 0
    sort_done_event.clear()
    exit_event.clear()

    init_modbus_record_file()
    log_modbus_record('record_file_created', detail=current_modbus_record_file)
    log_modbus_record('count_started', detail='Initial material counts')

    reset_machines()
    conveyors_on()
    write_coil(COIL_PUSHER_0, False)

    print('Full process started: MC0 blue / MC1 green together, Vision Sensor blue -> Pusher 0')
    print(
        'VISION_VALUE_REGISTER = Input Reg',
        VISION_VALUE_REGISTER,
        'blue_value =',
        VISION_BLUE_VALUE,
        'green_value =',
        VISION_GREEN_VALUE,
    )
    print(
        'BLUE_COUNT_SENSOR = Input',
        BLUE_COUNT_SENSOR,
        'GREEN_COUNT_SENSOR = Input',
        GREEN_COUNT_SENSOR,
    )
    log_modbus_record(
        'process_start',
        'input_register',
        VISION_VALUE_REGISTER,
        VISION_BLUE_VALUE,
        'Vision Sensor blue value',
    )

    production_thread = threading.Thread(target=production_loop, daemon=True)
    sorting_thread = threading.Thread(target=sorting_loop, daemon=True)
    modbus_record_thread = threading.Thread(target=modbus_record_loop, daemon=True)

    modbus_record_thread.start()
    production_thread.start()
    sorting_thread.start()

# Cell 8: auto start full process in Factory I/O
# Factory I/O must already be RUN and Modbus TCP/IP Server driver must be connected.

def ensure_factory_io_connected(retries=5, delay=1.0):
    global connected

    for attempt in range(1, retries + 1):
        try:
            connected = client.connect()
        except Exception as exc:
            connected = False
            print('Connection attempt', attempt, 'failed:', exc)

        if connected:
            print('Factory I/O Modbus connected')
            return True

        print('Waiting for Factory I/O Modbus connection...', attempt, '/', retries)
        tt.sleep(delay)

    raise RuntimeError(
        'Factory I/O Modbus connection failed. '
        'Check Factory I/O RUN mode, driver connection, IP address, and port 502.'
    )

def auto_start_factory_io(reset_outputs=True):
    global process_run

    ensure_factory_io_connected()

    if process_run:
        print('Previous process is running, stopping first')
        stop_all()
        tt.sleep(0.5)

    if reset_outputs:
        write_coils(0, [False] * 30)
        tt.sleep(0.3)

    factory_process()
    print('Factory I/O automatic process started')

def run_forever():
    auto_start_factory_io(reset_outputs=True)
    print('Running Factory I/O process. Press Ctrl+C to stop.')

    try:
        while process_run:
            tt.sleep(0.5)
    except KeyboardInterrupt:
        print('KeyboardInterrupt: stopping Factory I/O process')
    finally:
        try:
            stop_all()
        finally:
            try:
                client.close()
            except Exception:
                pass
        print('Factory I/O process stopped')


if __name__ == '__main__':
    run_forever()
