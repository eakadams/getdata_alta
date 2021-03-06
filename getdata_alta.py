#!/usr/bin/env python

# ALTA data transfer: Uses the iROD client to transfer data from ALTA
# Example usage: >> python getdata_alta.py 180316 004-010 00-36
# V.A. Moss (vmoss.astro@gmail.com)

###################################################################################################

from __future__ import print_function
import os
import sys
import time
import logging
import subprocess

FNULL = open(os.devnull, 'w')

###################################################################################################


def parse_list(spec):
    """Convert a string specification like 00-04,07,09-12 into a list [0,1,2,3,4,7,9,10,11,12]

    Args:
        spec (str): string specification

    Returns:
        List[int]

    Example:
        >>> parse_list("00-04,07,09-12")
        [0, 1, 2, 3, 4, 7, 9, 10, 11, 12]
        >>> parse_list("05-04")
        Traceback (most recent call last):
            ...
        ValueError: In specification 05-04, end should not be smaller than begin
    """
    ret_list = []
    for spec_part in spec.split(","):
        if "-" in spec_part:
            begin, end = spec_part.split("-")
            if end < begin:
                raise ValueError(
                    "In specification %s, end should not be smaller than begin" % spec_part)
            ret_list += range(int(begin), int(end) + 1)
        else:
            ret_list += [int(spec_part)]

    return ret_list

###################################################################################################


def get_alta_dir(date, task_id, beam_nr, alta_exception):
    """Get the directory where stuff is stored in ALTA. Takes care of different historical locations

    Args:
        date (str): date for which location is requested
        task_id (int): task id
        beam_nr (int): beam id
        alta_exception (bool): force 3 digits task id, old directory

    Returns:
        str: location in ALTA, including the date itself

    Examples:
        >>> get_alta_dir(180201, 5, 35, False)
        '/altaZone/home/apertif_main/wcudata/WSRTA18020105/WSRTA18020105_B035.MS'
        >>> get_alta_dir(180321, 5, 35, False)
        '/altaZone/home/apertif_main/wcudata/WSRTA180321005/WSRTA180321005_B035.MS'
        >>> get_alta_dir(181205, 5, 35, False)
        '/altaZone/archive/apertif_main/visibilities_default/181205005/WSRTA181205005_B035.MS'
    """
    #Test if data is in cold storage retrieval location
    altadir = "/altaZone/stage/apertif_main/visibilities_default/{date}{task_id:03d}/WSRTA{date}{task_id:03d}_B{beam_nr:03d}.MS.tar".format(**locals())
    cmd = "ils {}".format(altadir)
    testcold = subprocess.call(cmd.split(), stdout=FNULL, stderr=FNULL)
    
    if int(date) < 180216:
        return "/altaZone/home/apertif_main/wcudata/WSRTA{date}{task_id:02d}/WSRTA{date}{task_id:02d}_B{beam_nr:03d}.MS".format(**locals())
    elif int(date) < 181003 or alta_exception:
        return "/altaZone/home/apertif_main/wcudata/WSRTA{date}{task_id:03d}/WSRTA{date}{task_id:03d}_B{beam_nr:03d}.MS".format(**locals())
    elif int(str(date)+'%.3d' % task_id) == 190326001:
        return "/altaZone/ingest/apertif_main/visibilities_default/{date}{task_id:03d}/WSRTA{date}{task_id:03d}_B{beam_nr:03d}.MS".format(**locals())
    elif testcold == 0:
        return "/altaZone/stage/apertif_main/visibilities_default/{date}{task_id:03d}/WSRTA{date}{task_id:03d}_B{beam_nr:03d}.MS.tar".format(**locals())
    else:
        return "/altaZone/archive/apertif_main/visibilities_default/{date}{task_id:03d}/WSRTA{date}{task_id:03d}_B{beam_nr:03d}.MS".format(**locals())

###################################################################################################


def getstatus_alta(date, task_id, beam):
    """
    Funtion to check if the data is on ALTA.
    date (int or str): Date of the observation of the data. Format: YYMMDD
    task_id (int or str): ID number of the observation. Format: NNN
    beam (int or str): Beam number to copy. Format: NN
    return (bool): True if the file is available, False if not
    """
    altadir = get_alta_dir(date, int(task_id), int(beam), False)
    cmd = "ils {}".format(altadir)
    retcode = subprocess.call(cmd.split(), stdout=FNULL, stderr=FNULL)
    return retcode == 0

###################################################################################################


def getdata_alta(date, task_ids, beams, targetdir=".", tmpdir=".", alta_exception=False, check_with_rsync=True):
    """Download data from ALTA using low-level IRODS commands.
    Report status to slack

    Args:
        date (str): date of the observation
        task_ids (List[int] or int): list of task_ids, or a single task_id (int)
        beams (List[int] or int): list of beam numbers, or a single beam number (int)
        targetdir (str): directory to put the downloaded files
        tmpdir (str): directory for temporary files
        alta_exception (bool): force 3 digits task id, old directory
        check_with_rsync (bool): run rsync on the result of iget to verify the data got in
    """
    # Time the transfer
    start = time.time()
    logger = logging.getLogger("GET_ALTA")
    logger.setLevel(logging.DEBUG)

    if isinstance(task_ids, int):
        task_ids = [task_ids]
    if isinstance(beams, int):
        beams = [beams]

    if tmpdir == "":
        tmpdir = "."
    if targetdir == "":
        targetdir = "."

    if tmpdir[-1] != "/":
        tmpdir += "/"
    if targetdir[-1] != "/":
        targetdir += "/"

    logger.debug('Start getting data from ALTA')
    logging.debug('Beams: %s' % beams)

    for beam_nr in beams:

        logger.debug('Processing beam %.3d' % beam_nr)

        for task_id in task_ids:
            logger.debug('Processing task ID %.3d' % task_id)

            alta_dir = get_alta_dir(date, task_id, beam_nr, alta_exception)
            if alta_dir[-2:] == 'MS':
                cmd = "iget -rfPIT -X {tmpdir}WSRTA{date}{task_id:03d}_B{beam_nr:03d}-icat.irods-status --lfrestart " \
                      "{tmpdir}WSRTA{date}{task_id:03d}_B{beam_nr:03d}-icat.lf-irods-status --retries 5 {alta_dir} " \
                      "{targetdir}".format(**locals())
                logger.debug(cmd)
                subprocess.check_call(cmd, shell=True, stdout=FNULL, stderr=FNULL)
            #check for tar file and untar if needed:
            elif alta_dir[-3:] == 'tar':
                targetdir = targetdir[:-1]
                cmd = "iget -rfPIT -X {tmpdir}WSRTA{date}{task_id:03d}_B{beam_nr:03d}-icat.irods-status --lfrestart " \
                      "{tmpdir}WSRTA{date}{task_id:03d}_B{beam_nr:03d}-icat.lf-irods-status --retries 5 {alta_dir} " \
                      "{targetdir}.tar".format(**locals())
                logger.debug(cmd)
                subprocess.check_call(cmd, shell=True, stdout=FNULL, stderr=FNULL)
                head, tail = os.path.split(targetdir)
                tarcmd = "tar -xf {targetdir}.tar -C {head}".format(**locals())
                logger.debug(tarcmd)
                #subprocess.check_call(tarcmd, shell=True, stdout=FNULL, stderr=FNULL)
                #force untarring
                os.system(tarcmd)
                #have to rename
                head, tail = os.path.split(targetdir)
                print(head)
                print(os.path.join(head,'WSRTA{date}{task_id:03d}_B{beam_nr:03d}.MS'.format(**locals())))
                logger.debug("Rename untarred file to target name")
                os.rename(os.path.join(head,'WSRTA{date}{task_id:03d}_B{beam_nr:03d}.MS'.format(**locals())),targetdir)
                #remove tar file
                logger.debug("Removing tar file")
                os.remove("{targetdir}.tar".format(**locals()))


    os.system('rm -rf {tmpdir}*irods-status'.format(**locals()))

    # Add verification at the end of the transfer
    if check_with_rsync:
        for beam_nr in beams:
            logger.info('Verifying beam %.3d... ######' % beam_nr)

            for task_id in task_ids:
                logger.info('Verifying task ID %.3d...' % task_id)

                # Toggle for when we started using more digits:
                alta_dir = get_alta_dir(date, task_id, beam_nr, alta_exception)
                if targetdir == '.':
                    local_dir = "{targetdir}WSRTA{date}{task_id:03d}_B{beam_nr:03d}.MS"
                else:
                    local_dir = targetdir
                cmd = "irsync -srl i:{alta_dir} {local_dir} >> " \
                      "{tmpdir}transfer_WSRTA{date}{task_id:03d}_to_alta_verify.log".format(
                          **locals())

                subprocess.check_call(
                    cmd, shell=True, stdout=FNULL, stderr=FNULL)

        # Identify server details
        hostname = os.popen('hostname').read().strip()

        # Check for failed files
        for task_id in task_ids:
            logger.debug('Checking failed files for task ID %.3d' % task_id)

            cmd = 'grep N {tmpdir}transfer_WSRTA{date}{task_id:03d}_to_alta_verify.log | wc -l'.format(
                **locals())
            output = os.popen(cmd)
            n_failed_files = output.read().split()[0]
            logger.warning('Number of failed files: %s', n_failed_files)

    # Time the transfer
    end = time.time()

    # Print the results
    diff = (end - start) / 60.  # in min
    logger.debug("Total time to transfer data: %.2f min" % diff)
    logger.debug("Done getting data from ALTA")

###################################################################################################


if __name__ == "__main__":

    import doctest
    doctest.testmod()

    logging.basicConfig()

    args = sys.argv

    # Get date
    try:
        date = args[1]
    except Exception:
        raise Exception("Date required! Format: YYMMDD e.g. 180309")

    # Get ID range
    try:
        irange = args[2]
    except Exception:
        raise Exception("ID range required! Format: NNN-NNN e.g. 002-010")

    # Get beam range
    try:
        brange = args[3]
    except Exception:
        raise Exception("Beam range required! Format: NN-NN e.g. 00-37")

    # Get beams
    try:
        alta_exception = args[4]
        if alta_exception == 'Y':
            alta_exception = True
        else:
            alta_exception = False
    except Exception:
        alta_exception = False

    # Now with all the information required, loop through beams
    beams = parse_list(brange)

    # Now with all the information required, loop through task_ids
    task_ids = parse_list(irange)

    getdata_alta(date, task_ids, beams, ".", ".", alta_exception)
