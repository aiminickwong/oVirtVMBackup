#!/usr/bin/python

import os

from ovirtvmbackup import OvirtBackup, rename_clone
from colorama import init, Fore
import argparse
import sys
import ConfigParser
import subprocess
import time

init(autoreset=True)

config_file='/etc/ovirt-vm-backup/ovirt-vm-backup.conf'
vms_path = "/master/vms/"
images_path = "/images/"

def export(conn, vm_name, new_name, description, export_domain):
    conn.log_event(vm_name,'Backup Process for VM \''+vm_name+'\' has started','normal')
    print(Fore.GREEN + "Export virtual machine {}".format(vm_name))

    if (conn.if_exists_vm(vm=vm_name)):
        if (conn.if_exists_vm(vm=new_name)):
            print(Fore.RED + "Virtual Machine {} Backup already exists".format(new_name))
            conn.log_event(vm_name,'Backup VM \''+vm_name+'\' Failed, '+new_name+' already exist','error')
            print "HOLA"
        else:
            print(Fore.YELLOW + "creating snapshot")
            conn.create_snap(desc=description, vm=vm_name)
            print(Fore.GREEN + "\ncreate snapshot successful")
            print(Fore.YELLOW + "creating new virtual machine {}".format(new_name))
            conn.create_vm_to_export(vm=vm_name, new_name=new_name, desc=description)
            print(Fore.GREEN + "\ncreate virtual machine {} successful".format(new_name))
            print(Fore.YELLOW + "Activating Export Domain {}".format(export_domain))
            conn.active_export(vm=vm_name, export_name=export_domain)
            print(Fore.GREEN + "Export domain {} successful activated".format(export_domain))
            print(Fore.YELLOW + "Export Virtual Machine {}".format(new_name))
            export_dom = conn.get_export_domain(vm=vm_name)
            conn.export_vm(new_name, export_dom)
            print(Fore.GREEN + "\nExport Virtual Machine {} successful".format(export_domain))
            print(Fore.YELLOW + "Moving export to another location")
            conn.log_event(vm_name,'Backup VM preparing \''+vm_name+'\' for storage','normal')
            conn.create_dirs(vm_name=vm_name, export_path=path_export, images=images_path, vms=vms_path)
            conn.do_mv(vm=new_name, export_path=path_export, images=images_path, vms=vms_path)
            # trabajado con ovf's
            conn.log_event(vm_name,'Backup VM keeping \''+vm_name+'\' original configuration','normal')
            print(Fore.YELLOW + "Change id's and paths")
            conn.get_running_ovf(vm=vm_name, desc=description, path=path_export)
            export_xml = conn.export_xml_path(path=path_export, vm=vm_name, find_path=vms_path)
            original_xml = conn.export_xml_path(path=path_export, vm=vm_name)
            xml_obj = conn.add_storage_id_xml(original_xml, export_xml)
            ovf_final = os.path.basename(original_xml)[8:]
            vms_path_save = path_export + vm_name + vms_path
            conn.save_new_ovf(path=vms_path_save, name=ovf_final, xml=xml_obj)
            conn.delete_tmp_ovf(path=path_export + vm_name + "/running-" + ovf_final)
            rename_clone(export_xml, vms_path_save + conn.api.vms.get(vm_name).id + "/" + ovf_final, path_export + vm_name + images_path)
            print(Fore.GREEN + "Move successful")
            print(Fore.YELLOW + "Remove snap and Virtual Machine")
            # Eliminando snapshot y {vm}-snap
            conn.delete_snap(vm=vm_name, desc=description)
            conn.delete_tmp_vm(new_name=new_name)
            print(Fore.GREEN + "process finished successful")
            conn.log_event(vm_name,'Backup VM \''+vm_name+'\' ready for storage','normal')
    else:
        print(Fore.RED + "Virtual Machine {} doesn't exists".format(vm_name))
        exit(1)

def vm_import(name):
    print("Import virtual machine {}".format(name))
    pass

def du(path):
  return subprocess.check_output(['du','-sh', path]).split()[0].decode('utf-8')

def load_config(path):
    config = ConfigParser.ConfigParser()
    config.read(path)
    return dict(config.items("general"))

def change_meta(path):
    for image in os.listdir(path):
        image_id=image
        for file in os.listdir(path+'/'+image_id):
            if file.endswith(".meta"):
                subprocess.call(['sed','-i','s/^IMAGE=.*/IMAGE='+image_id+'/g',path+image_id+'/'+file])    

def upload_tsm(path):
    command=subprocess.call(['sudo','dsmc','selective',path,'-subdir=yes'],cwd='/tmp') 
    return command.returncode

def main():
    if ( len(sys.argv) != 2):
      print ("Syntax: %s VMNAME") % (sys.argv[0] )
      sys.exit(2)
    if not ( os.path.isfile(config_file) ):
      print "No configuration file found"
      sys.exit(1)
    
    general=load_config(config_file)
    global path_export
    global dsmc
    path_export=general['exportpath']
    dsmc=general['dsmc']
    vmname=sys.argv[1]
    new_name=vmname+'-snap'
    description = "oVirtBackup"
    url = "https://" + general['manager']
    print url
    print description
    is_export=True
    oVirt = OvirtBackup(url, general['api_user'], general['api_pass'])
    print(Fore.YELLOW + "trying auth...")
    try:
        oVirt.connect()
        print(Fore.GREEN + "auth OK")
        export(
        conn=oVirt, vm_name=vmname, new_name=new_name,
        description=description, export_domain=general['export']
        )
    except:
        oVirt.log_event(vmname,'Backup VM \''+vmname+'\' Failed','error')
    oVirt.log_event(vmname,'Preparing VM '+vmname+' for TSM Backup','normal')
    change_meta(path_export+vmname+images_path)
    oVirt.log_event(vmname,'Uploading VM '+vmname+' to TSM','normal')
    try:
        upload_tsm(path_export+vmname)
        oVirt.log_event(vmname,'Uploading VM '+vmname+' to TSM has been completed','normal')
    except:
        oVirt.log_event(vmname,'Uploading VM '+vmname+' to TSM has failed','error')
        date=time.strftime('%Y-%m-%d-%H%M%S',time.localtime())
        tempdir=path_export+vmname+'-'+date
        os.rename(path_export+vmname,tempdir)
        oVirt.log_event(vmname,'Uploading VM '+vmname+' to TSM has failed and moved to '+tempdir,'error')

        

if __name__ == '__main__':
    main()