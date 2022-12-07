import os
import subprocess
from subprocess import Popen, PIPE
import multiprocessing
import time


DEBUG = False

class AVDManager:
    # home = os.getenv("HOME")
    # android_home = os.path.join(home, "Android/Sdk")
    android_home = os.getenv("ANDROID_HOME")

    bin_dir = os.path.join(android_home, "tools/bin")
    # full_location = location.replace("~", home)


    if not os.path.isdir(bin_dir):
        raise Exception(f"{bin_dir} folder does not exist or You don't have permission to access")

    avd_manager_path = os.path.join(bin_dir, "avdmanager")  # vs ~/Android/Sdk/tools/bin/avdmanager
    if not os.path.isfile(avd_manager_path):
        raise Exception(f"'avdmanager' does not exist (OR no permission) in path {bin_dir}")
    
    def __init__(self):
        self.current_command = ""

    def _run_command(self, command, wait=True):  # wait false uses multiprocessing
        self.current_command = command
        if DEBUG:
            print(f"CURRENT COMMAND: {command}")
        if wait is True:
            commandline_process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
            if commandline_process.stderr:
                raise Exception(f"Error in running command '{command}': {str(commandline_process.stderr)}")
            else:
                out = commandline_process.stdout.read().decode('UTF-8').strip()
                return out
        elif wait is False:
            process_01 = multiprocessing.Process(target=lambda: os.system(command))
            process_01.start()

            self.child_process = process_01

            # process_01.kill()
            
            return f"Multiprocess started! PID in background = {process_01.pid}"
            # return f"Os.system output is {out} [Non-Zero output means some error occured]"
        else:
            raise Exception("Wait set is neither True or False.\
                 Please check if you have added a boolean value to the wait param")

    def list_avds(self):
        out = self._run_command(f"{self.avd_manager_path} list avd")
        _, avd_section = out.split("Available Android Virtual Devices:")
        avd_infos = [sec.strip('-').strip() for sec in avd_section.split("---")]

        avds = []
        for avd_info in avd_infos:
            avd = dict()
            for avd_line in avd_info.splitlines():
                if avd_line.count(":") == 1:
                    k, v = [item.strip() for item in avd_line.split(":")]
                    avd[k] = v
                elif avd_line.count(":") == 2:
                    line_break = " Tag/"  # "Based on: Android API 31 Tag/ABI: google_apis/x86_64"
                    if line_break in avd_line:
                        break_point = avd_line.find(line_break)
                        for broken_line in [avd_line[break_point:], avd_line[:break_point]]:
                            k, v = [item.strip() for item in broken_line.split(":")]
                            avd[k] = v
                    else:
                        print(f"The line '{avd_line}' is ignored from parsing due to linebreak text is not found")
                else:
                    print(f"The line '{avd_line}' is ignored from parsing")
                    
            if avd: avds.append(avd)

        return avds



    '''To undestand why use of Popen and proc.communicate() in the current scenario of netcat commands,
    please see https://stackoverflow.com/questions/22250893/capture-segmentation-\
    fault-message-for-a-crashed-subprocess-no-out-and-err-af/22253472#22253472
    '''
    def __run_shell_command_n_get_output_in_list_of_lines(self, cmd):
        proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        out, err = proc.communicate()
        out_lines = [] if err else out.decode().strip().splitlines()
        if err: 
            pass
            # logger.critical(f'The command execution for "{cmd}" returns error code: {err}')
        return out_lines


    def get_adb_devices(self):  # adb_device_id looks like 'emulator-5556'
        # logger.debug("Getting all running ADB devices")
        cmd = f'''adb devices'''
        out_lines = self.__run_shell_command_n_get_output_in_list_of_lines(cmd)
        adb_devices = [line.rstrip('\tdevice').strip() for line in out_lines if line.endswith('\tdevice')]
        # logger.debug(f"Found {len(adb_devices)} ADB devices. They are {', '.join(adb_devices)}")
        return adb_devices


    def get_avd_name_from_adb_device_id(self, adb_device_id):
        port_number = adb_device_id.split('-')[-1]  # eg: emulator-5556
        cmd = f'''echo "avd name" | nc -w 1 localhost {port_number}'''

        out_lines = self.__run_shell_command_n_get_output_in_list_of_lines(cmd)
        avd_name = out_lines[-2] if (out_lines[-1] == "OK") and (out_lines[-3] == "OK") else None
        return avd_name


    def get_adb_devices_n_corresponding_avd_names(self) -> dict:
        """returns something like this '{'emulator-5556': 'Nexus_6_API_31'}'"""
        # logger.debug("Getting ADB devices and their corresponding AVD names by netcating into ADB devices")
        emulators = [adb_device for adb_device in self.get_adb_devices() if adb_device.startswith('emulator')] # to avoid devices other than emulators
        adb_devices_to_avd_name_map = {adb_device_id: self.get_avd_name_from_adb_device_id(adb_device_id) for adb_device_id in emulators}
        # logger.info(f"ADB devices and their AVD names: {adb_devices_to_avd_name_map}")
        
        for adb_device_id in adb_devices_to_avd_name_map:
            if adb_devices_to_avd_name_map[adb_device_id] is None:
                # logger.error(f"AVD name for ADB device id '{adb_device_id}' is None. Please debug the issue!")
                raise Exception(f"AVD name for ADB device id '{adb_device_id}' is None. Please debug the issue!")
                # this might not be good for later purposes. Deal this later
        
        return adb_devices_to_avd_name_map


    def get_adb_device_id_from_avd_name(self, name):

        # two times checking due to adb devices does not show up some times -- so use while loop
        number_of_tries = 5
        for _ in range(number_of_tries):
            adb_id_2_avd_mapper = self.get_adb_devices_n_corresponding_avd_names() 
            for adb_id, avd_name in adb_id_2_avd_mapper.items():
                if avd_name == name:
                    return adb_id
        else:
            raise Exception("The AVD device not found.\
                Make sure if emulator with corresponding AVD is strated or created\
                    please rerun the command if you are sure\
                        if there is started emulator with this name")



class Emulator(AVDManager):

    def __init__(self, name, avd_manager_path=None, emulator_bin_path=None):
        super().__init__()

        self.name = name

        self.exists = False # if exist or deleted
        self.is_started = False

        if avd_manager_path:
            self.android_home = self._run_command("echo $ANDROID_HOME")
            self.avd_manager_path = avd_manager_path
        
        if emulator_bin_path:
            self.emulator_bin_path = emulator_bin_path
        else:
            self.emulator_bin_path = os.path.join(self.android_home, "emulator/emulator")
        

        # self.delete_command_template = "del {name}" 
    
    def get_name(self,):
        return self.name

    def get_adb_device_id(self):
        if self.is_started:
            return super().get_adb_device_id_from_avd_name(self.name)
        else:
            raise Exception("The AVD is not started and running now")

    def create(self, 
            api_level = 31,  # default should be set after discussion
            instruction_set = 64,  # or 32 bit
            forced_recreate=True, 
            silent_mode_enabled = True,
        ):

        if self.exists is True:  # this allows not to create one more within in same emulator object
            raise Exception("The AVD (Android Virtual Device) already exists")

        answer_create_hardware_profile = 'no'
        architecture = "x86_64" if instruction_set == 64 else "x86"

        sdk_id = f"system-images;android-{api_level};google_apis;{architecture}"

        create_cmd = f'''echo "{answer_create_hardware_profile}" | {self.avd_manager_path}'''+\
            f'''{' --silent' if silent_mode_enabled else ''} create avd{' --force' if forced_recreate is True else ''}'''+\
                f''' --name {self.name} --package "{sdk_id}"'''+\
                    f''' --abi google_apis/{architecture}  --device "Nexus 6P"'''

        out = self._run_command(create_cmd)
        self.exists = True
        return out

    def start(self, resolution="1080x2340"):
        if self.exists is False:
            if self.name in self.get_adb_devices_n_corresponding_avd_names().values():
                # print already started AVD
                raise Exception("The AVD is already started. Because curresponding ADB device id is found")
            
            elif self.name in [av['Name'] for av in self.list_avds()]:
                print(f"The AVD does not exist in the current instance but exists in the machine")
                print(f"Trying to start that preexisting AVD")
            
            else:
                raise Exception(f"The emulator '{self.name}' does not exist")
        if self.is_started:
            raise Exception(f"The emulator '{self.name}' already started")
        start_cmd = f'''{self.emulator_bin_path} -avd {self.name}'''  # -skin {resolution}
        print(start_cmd)
        out = self._run_command(start_cmd, wait=False)
        self.is_started = True
        self.exists = True

        # waiting for enlist the emulator id in adb devices
        CONFIGURED_SLEEP_SECONDS_AFTER_FIRING_THE_EMULATOR_START_COMMAND = 20  # add this configuration
        print(f"Waiting for pre-defined sleep time of {CONFIGURED_SLEEP_SECONDS_AFTER_FIRING_THE_EMULATOR_START_COMMAND}"+\
            " seconds to enlist current emulator in adb devices list...")
        time.sleep(CONFIGURED_SLEEP_SECONDS_AFTER_FIRING_THE_EMULATOR_START_COMMAND)

        # waiting for fully booting up the device
        dots_number = 0
        self.adb_id = self.get_adb_device_id()
        print(f"Waiting to complete the bootup process for emulator with adb id '{self.adb_id}' and with AVD name '{self.name}'")
        while True:
            print(f"Waiting" + (dots_number * "."), end='\r')
            dots_number += 1
            # ret = self._run_command(f'''adb -s {self.adb_id} shell getprop sys.boot_completed''')
            ret = self.execute("getprop sys.boot_completed")
            try:
                return_number = int(ret)
            except:
                return_number = 0
            
            if return_number != 1:
                time.sleep(1)
                # print(ret)
            else:
                print("\nTHE DEVICE is fully booted!")
                break
        return out

    
    def execute(self, command): # adb -s emulator-5556 shell
        """execute ADB shell commands"""
        return self._run_command(f'''adb -s {self.adb_id} shell {command}''')


    def wait(self, seconds):
        print(f"Waiting for {seconds} seconds")
        time.sleep(seconds)


    def kill(self):
        if self.exists is False:
            raise Exception(f"The emulator '{self.name}' does not exist")
        if self.is_started is False:
            raise Exception(f"The emulator '{self.name}' not started")
        self.child_process.kill()
        out = self._run_command(f'''adb -s {self.get_adb_device_id()} emu kill''')
        self.is_started = False
        return out


    def delete(self, silent_mode_enabled=True):
        if self.exists is True:
            if self.is_started:
                self.kill()
            
            # delete command
            delete_cmd = f"{self.avd_manager_path}{' --silent' if silent_mode_enabled else ''} delete avd -n {self.name}"

            out = self._run_command(delete_cmd)
            self.exists = False
            return out
        else:
            raise Exception("This AVD does not exist - it means either it is not created yet or already deleted!")


