"""Factory I/O color sorting process.

Run this file with:
    python pyfa-project.py

Factory I/O must be in RUN mode and the Modbus TCP/IP Server driver must be connected.
Press Ctrl+C to stop all outputs safely.
"""

# Cell 1: Modbus connection
from pymodbus.client import ModbusTcpClient
import time as tt
import threading

IP_ADDRESS = '210.119.14.76'
PORT = 502
UNIT_ID = 1

client = ModbusTcpClient(IP_ADDRESS, port=PORT)
connected = client.connect()
print('connected =', connected)

# Cell 2: I/O mapping from Factory I/O driver
# Updated for the current Factory I/O driver screen.
# Input 0 = Vision Sensor 0, configured to detect BLUE products only.
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

REG_MC0_PROGRESS = 0
REG_MC1_PROGRESS = 1

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

# Vision Sensor 0 must be configured in Factory I/O to detect BLUE only.
# Green must pass with Input 0 = False.
VISION_BLUE_SENSOR = IN_VISION_SENSOR_0
BLUE_SENSOR = VISION_BLUE_SENSOR
BLUE_SENSOR_ACTIVE_STATE = True
EXIT_SENSOR = IN_SENSOR_4

# If Vision Sensor 0 turns False when blue is detected, change this to False.
# Current Factory I/O driver image normally uses True when Vision Sensor 0 detects blue.
VISION_SENSOR_DEBUG = True

# Vision Sensor 0 alone decides whether the product is blue.
# Input 0 True -> blue -> pusher ON. Input 0 False -> green/other -> pusher OFF.

EMIT_TIME = 0.35
START_HOLD = 0.5
PRODUCE_HOLD = 10.0
WAIT_BUSY_TIMEOUT = 12.0

FEED_TO_MC0_TIME = 4.5
FEED_TO_MC1_TIME = 5.5
MACHINE_TIMEOUT = 20.0
WAIT_SORT_DONE_TIMEOUT = 35.0
REPEAT_DELAY = 0.8

MC0_PRODUCT_NAME = 'blue product lid/base line'
MC1_PRODUCT_NAME = 'green product lid/base line'

SENSOR_CONFIRM_TIME = 0.00

# If blue is pushed too early, increase this by 0.05~0.10.
# If blue passes without being pushed, decrease this toward 0.00.
BLUE_TO_PUSHER_DELAY = 0.20
PUSH_TIME = 2.00
PUSH_RETURN_TIME = 1.40
PUSH_CYCLE_GAP = 0.80
PUSH_EXTEND_TIMEOUT = 1.50
PUSH_RETRACT_TIMEOUT = 2.00
PUSH_COOLDOWN = 0.80

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
blue_push_busy = False
blue_sensor_latched = False
sort_done_event = threading.Event()
exit_event = threading.Event()
machining_lock = threading.Lock()
active_machining_count = 0

# Cell 4: Modbus helper functions
def _is_error(result):
    return hasattr(result, 'isError') and result.isError()

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
    try:
        result = client.write_coil(addr, bool(value), slave=UNIT_ID)
    except TypeError:
        result = client.write_coil(addr, bool(value))
    if _is_error(result):
        raise RuntimeError(f'Coil {addr} write failed')
    return result

def write_coils(addr, values):
    try:
        result = client.write_coils(addr, values, slave=UNIT_ID)
    except TypeError:
        result = client.write_coils(addr, values)
    if _is_error(result):
        raise RuntimeError(f'Coils from {addr} write failed')
    return result

def write_register(addr, value):
    try:
        result = client.write_register(addr, int(value), slave=UNIT_ID)
    except TypeError:
        result = client.write_register(addr, int(value))
    if _is_error(result):
        raise RuntimeError(f'Holding register {addr} write failed')
    return result

def write_registers(addr, values):
    values = [int(v) for v in values]
    try:
        result = client.write_registers(addr, values, slave=UNIT_ID)
    except TypeError:
        result = client.write_registers(addr, values)
    if _is_error(result):
        raise RuntimeError(f'Holding registers from {addr} write failed')
    return result

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
    global process_run, machine_repeat_run
    process_run = False
    machine_repeat_run = False
    write_coils(0, [False] * 30)
    print('All outputs stopped')

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

# Cell 7: full process - MC0/MC1 together, Vision Sensor blue only pusher
# MC0 = blue product line, MC1 = green product line.
# MC0 and MC1 run at the same time.
# Vision Sensor 0 is the final color decision:
#   Input 0 True  -> blue product -> Pusher 0 Coil 5 ON
#   Input 0 False -> green product -> Pusher 0 OFF and pass


def read_vision_sensor_raw():
    return read_input(BLUE_SENSOR)


def is_blue_detected():
    return read_vision_sensor_raw() == BLUE_SENSOR_ACTIVE_STATE


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
    if VISION_SENSOR_DEBUG:
        print(
            'Vision Sensor 0 raw =', raw_value,
            'active_state =', BLUE_SENSOR_ACTIVE_STATE,
            'blue_detected =', raw_value == BLUE_SENSOR_ACTIVE_STATE,
        )


def machine_job(color):
    if color == 'blue':
        print('Starting MC0:', MC0_PRODUCT_NAME)
        feed_mc0_and_run()
        print('MC0 blue processed product released')
    elif color == 'green':
        print('Starting MC1:', MC1_PRODUCT_NAME)
        feed_mc1_and_run()
        print('MC1 green processed product released: pusher OFF')
        write_coil(COIL_PUSHER_0, False)


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
    print('Cycle start: MC0 blue and MC1 green run together')
    conveyors_on()

    blue_thread = threading.Thread(target=machine_job, args=('blue',), daemon=True)
    green_thread = threading.Thread(target=machine_job, args=('green',), daemon=True)

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
    # Fixed one-shot cycle: ON once, hold fixed time, OFF once, fixed return time.
    # This avoids shorter/weak pusher strokes caused by limit sensor timing drift.
    print('Vision Sensor 0 BLUE -> fixed Pusher 0 cycle')

    conveyors_on()
    write_coil(COIL_PUSHER_0, True)
    tt.sleep(PUSH_TIME)

    write_coil(COIL_PUSHER_0, False)
    tt.sleep(PUSH_RETURN_TIME)

    tt.sleep(PUSH_CYCLE_GAP)
    print('Fixed blue pusher cycle done')


def delayed_blue_push_from_vision():
    global blue_push_busy

    if blue_push_busy:
        print('Vision Sensor blue detected, but Pusher 0 is already moving')
        return

    blue_push_busy = True

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
        blue_push_busy = False


def schedule_blue_push_from_vision():
    global blue_push_thread

    if blue_push_busy:
        print('Vision Sensor 0 detected blue, but pusher is already busy')
        return

    print('Vision Sensor 0 detected BLUE: scheduling Pusher 0')
    blue_push_thread = threading.Thread(target=delayed_blue_push_from_vision, daemon=True)
    blue_push_thread.start()


def sorting_loop():
    global blue_sensor_latched

    prev_exit = False
    prev_raw = None
    blue_sensor_latched = False

    write_coil(COIL_PUSHER_0, False)
    print('Sorting loop started: Vision Sensor 0 blue -> Pusher 0, green passes')

    while process_run:
        conveyors_on()

        raw_blue = read_vision_sensor_raw()
        blue_now = raw_blue == BLUE_SENSOR_ACTIVE_STATE
        exit_sensor = read_input(EXIT_SENSOR)

        if raw_blue != prev_raw:
            print_vision_sensor_state(raw_blue)
            prev_raw = raw_blue

        if blue_now:
            if not blue_sensor_latched and wait_stable_blue_sensor():
                blue_sensor_latched = True
                schedule_blue_push_from_vision()
        else:
            blue_sensor_latched = False

        if exit_sensor and not prev_exit:
            print('Product reached exit')
            exit_event.set()

        if not blue_push_busy:
            write_coil(COIL_PUSHER_0, False)

        prev_exit = exit_sensor
        tt.sleep(SCAN_TIME)


def factory_process():
    global process_run, production_thread, sorting_thread
    global blue_push_busy, blue_sensor_latched, active_machining_count

    process_run = True
    blue_push_busy = False
    blue_sensor_latched = False
    active_machining_count = 0
    sort_done_event.clear()
    exit_event.clear()

    reset_machines()
    conveyors_on()
    write_coil(COIL_PUSHER_0, False)

    print('Full process started: MC0/MC1 together, Vision Sensor blue -> Pusher 0')
    print('BLUE_SENSOR = Input', BLUE_SENSOR, 'active_state =', BLUE_SENSOR_ACTIVE_STATE)

    production_thread = threading.Thread(target=production_loop, daemon=True)
    sorting_thread = threading.Thread(target=sorting_loop, daemon=True)

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
