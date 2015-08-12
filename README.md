# A bioinformatics pipeline based on [Ruffus](http://www.ruffus.org.uk/)

Author: Bernie Pope (bjpope@unimelb.edu.au)

complexo_pipeline is based on the [Ruffus](http://www.ruffus.org.uk/) library for writing bioinformatics pipelines. Its features include:

 * Job submission on a cluster using DRMAA (currently only tested with SLURM).
 * Job dependency calculation and checkpointing.
 * Pipeline can be displayed as a flowchart.
 * Re-running a pipeline will start from the most up-to-date stage. It will not redo previously completed tasks.

## License

3 Clause BSD License. See LICENSE.txt in source repository.

## Installation

#### External dependencies

`complexo_pipeline` depends on the following programs and libraries:

 * [python](https://www.python.org/download/releases/2.7.5/) (version 2.7.5)
 * [DRMAA](http://www.drmaa.org/) for submitting jobs to the cluster (it uses the Python wrapper to do this). 
   You need to install your own `libdrama.so` for your local job submission system. There are versions
   available for common schedulers such as Torque/PBS, [SLURM](http://apps.man.poznan.pl/trac/slurm-drmaa) and so on.
 * [bwa](http://bio-bwa.sourceforge.net/) for aligning reads to the reference genome (version 0.7.10)
 * [gatk](https://www.broadinstitute.org/gatk/) Genome Analysis Toolkit (version 3.3-0)
 * [samtools](http://www.htslib.org/) (version 0.1.2)
 * [picard](http://broadinstitute.github.io/picard/) (version 1.127)

You will need to install these dependencies yourself.

I recommend using a virtual environment:

```
cd /place/to/install
virtualenv complexo_pipeline
source complexo_pipeline/bin/activate
pip install -U https://github.com/bjpop/complexo_pipeline
```

If you don't want to use a virtual environment then you can just install with pip:

```
pip install -U https://github.com/bjpop/complexo_pipeline
```

## Worked example

The `example` directory in the source distribution contains a small dataset to illustrate the use of the pipeline.

#### Get a copy of the source distribution

```
cd /path/to/test/directory
git clone https://github.com/bjpop/complexo_pipeline
```

#### Install `complexo_pipeline` as described above

#### Get a reference genome.

```
cd complexo_pipeline/example
mkdir reference
# copy your reference into this directory, or make a symbolic link
# call it reference/genome.fa
```

#### Tell Python where your DRMAA library is 

For example (this will depend on your local settings):

```
export DRMAA_LIBRARY_PATH=/usr/local/slurm_drmaa/1.0.7-gcc/lib/libdrmaa.so
```

#### Run `complexo_pipeline` and ask it what it will do next

```
complexo_pipeline -n --verbose 3
```

#### Generate a flowchart diagram

```
complexo_pipeline --flowchart pipeline_flow.png --flowchart_format png
```

#### Run the pipeline

```
complexo_pipeline --use_threads --log_file pipeline.log --jobs 2 --verbose 3
```

## Usage

You can get a summary of the command line arguments like so:

```
complexo_pipeline -h
usage: complexo_pipeline [-h] [--verbose [VERBOSE]] [-L FILE] [-T JOBNAME]
                         [-j N] [--use_threads] [-n] [--touch_files_only]
                         [--recreate_database] [--checksum_file_name FILE]
                         [--flowchart FILE] [--key_legend_in_graph]
                         [--draw_graph_horizontally]
                         [--flowchart_format FORMAT] [--forced_tasks JOBNAME]
                         [--config CONFIG] [--jobscripts JOBSCRIPTS]
                         [--version]

Variant calling pipeline

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG       Pipeline configuration file in YAML format, defaults
                        to pipeline.config
  --jobscripts JOBSCRIPTS
                        Directory to store cluster job scripts created by the
                        pipeline, defaults to jobscripts
  --version             show program's version number and exit

Common options:
  --verbose [VERBOSE], -v [VERBOSE]
                        Print more verbose messages for each additional
                        verbose level.
  -L FILE, --log_file FILE
                        Name and path of log file

pipeline arguments:
  -T JOBNAME, --target_tasks JOBNAME
                        Target task(s) of pipeline.
  -j N, --jobs N        Allow N jobs (commands) to run simultaneously.
  --use_threads         Use multiple threads rather than processes. Needs
                        --jobs N with N > 1
  -n, --just_print      Don't actually run any commands; just print the
                        pipeline.
  --touch_files_only    Don't actually run any commands; just 'touch' the
                        output for each task to make them appear up to date.
  --recreate_database   Don't actually run any commands; just recreate the
                        checksum database.
  --checksum_file_name FILE
                        Path of the checksum file.
  --flowchart FILE      Don't run any commands; just print pipeline as a
                        flowchart.
  --key_legend_in_graph
                        Print out legend and key for dependency graph.
  --draw_graph_horizontally
                        Draw horizontal dependency graph.
  --flowchart_format FORMAT
                        format of dependency graph file. Can be 'svg', 'svgz',
                        'png', 'jpg', 'psd', 'tif', 'eps', 'pdf', or 'dot'.
                        Defaults to the file name extension of --flowchart
                        FILE.
  --forced_tasks JOBNAME
                        Task(s) which will be included even if they are up to
                        date.
```

## Configuration file

You must supply a configuration file for the pipeline in YAML format.

Here is an example:

```
# Default settings for the pipeline stages.
# These can be overridden in the stage settings below.

defaults:
    # Number of CPU cores to use for the task
    cores: 1
    # Maximum memory in gigabytes for a cluster job
    mem: 4
    # VLSCI account for quota
    account: VRXXXX
    queue: VRYYYY
    # Maximum allowed running time on the cluster in Hours:Minutes
    walltime: '1:00'
    # Load modules for running a command on the cluster.
    modules: 
    # Run on the local machine (where the pipeline is run)
    # instead of on the cluster. False means run on the cluster.
    local: False

# Stage-specific settings. These override the defaults above.
# Each stage must have a unique name. This name will be used in
# the pipeine to find the settings for the stage.

stages:
    # Align paired end FASTQ files to the reference
    align_bwa:
        cores: 8
        walltime: '8:00'
        mem: 32 
        modules:
            - 'bwa-intel/0.7.12'
            - 'samtools-intel/1.1'
   
    # Sort the BAM file with Picard 
    sort_bam_picard:
        walltime: '10:00'
        mem: 30 
        modules:
            - 'picard/1.127'
    
    # Mark duplicate reads in the BAM file with Picard
    mark_duplicates_picard:
        walltime: '10:00'
        mem: 30 
        modules:
            - 'picard/1.127'
    
    # Generate chromosome intervals using GATK 
    chrom_intervals_gatk:
        cores: 8
        walltime: '10:00'
        mem: 30 
        modules:
            - 'gatk/3.4-46'
    
    # Local realignment using GATK
    local_realignment_gatk:
        walltime: '10:00'
        mem: 30 
        modules:
            - 'gatk/3.4-46'

    # Local realignment using GATK
    base_recalibration_gatk:
        walltime: '10:00'
        mem: 30 
        modules:
            - 'gatk/3.4-46'

    # Print reads using GATK
    print_reads_gatk:
        walltime: '10:00'
        mem: 30 
        modules:
            - 'gatk/3.4-46'

    # Call variants using GATK
    call_variants_gatk:
        cores: 8
        walltime: '10:00'
        mem: 30 
        modules:
            - 'gatk/3.4-46'

    # Combine G.VCF files for all samples using GATK
    combine_gvcf_gatk:
        cores: 1
        walltime: '10:00'
        mem: 30 
        modules:
            - 'gatk/3.4-46'

    # Genotype G.VCF files using GATK
    genotype_gvcf_gatk:
        cores: 8 
        walltime: '10:00'
        mem: 30 
        modules:
            - 'gatk/3.4-46'

    # SNP recalibration using GATK 
    snp_recalibrate_gatk:
        cores: 8 
        walltime: '10:00'
        mem: 30 
        modules:
            - 'gatk/3.4-46'

    # INDEL recalibration using GATK  
    indel_recalibrate_gatk:
        cores: 8 
        walltime: '10:00'
        mem: 30 
        modules:
            - 'gatk/3.4-46'

    # Apply SNP recalibration using GATK 
    apply_snp_recalibrate_gatk:
        cores: 8 
        walltime: '10:00'
        mem: 30 
        modules:
            - 'gatk/3.4-46'

    # Apply INDEL recalibration using GATK 
    apply_indel_recalibrate_gatk:
        cores: 8 
        walltime: '10:00'
        mem: 30 
        modules:
            - 'gatk/3.4-46'

    # Combine variants using GATK 
    combine_variants_gatk:
        cores: 8 
        walltime: '10:00'
        mem: 30 
        modules:
            - 'gatk/3.4-46'

    # Select variants using GATK 
    select_variants_gatk:
        cores: 8 
        walltime: '10:00'
        mem: 30 
        modules:
            - 'gatk/3.4-46'

mills_grch37: reference/Mills_and_1000G_gold_standard.indels.b37.vcf
one_k_g_grch37_indels: reference/1000G_phase1.indels.b37.vcf
one_k_g_snps: reference/1000G_omni2.5.b37.vcf
one_k_g_highconf_snps: reference/1000G_phase1.snps.high_confidence.b37.vcf
one_k_g_indels: reference/1000G_phase1.indels.b37.vcf
hapmap: reference/hapmap_3.3.b37.vcf
interval_grch37: reference/Broad.human.exome.b37.interval_list
dbsnp_grch37: reference/dbsnp_138.b37.vcf
CEU_mergeGvcf: reference/CEU_mergeGvcf.vcf
FIN_mergeGvcf: reference/FIN_mergeGvcf.vcf
GBR_mergeGvcf: reference/GBR_mergeGvcf.vcf

# The Human Genome in FASTA format.

ref_grch37: reference/human_g1k_v37_decoy.fasta 

# The input FASTQ files.

fastqs:
   - fastqs/sample1_R1.fastq.gz
   - fastqs/sample1_R2.fastq.gz
   - fastqs/sample2_R1.fastq.gz
   - fastqs/sample2_R2.fastq.gz
```
