'''
Individual stages of the pipeline implemented as functions from
input files to output files.

The run_stage function knows everything about submitting jobs and, given
the state parameter, has full access to the state of the pipeline, such 
as config, options, DRMAA and the logger.
'''

from utils import safe_make_dir
from runner import run_stage
import os

PICARD_JAR = '$PICARD_HOME/lib/picard.jar'
GATK_JAR = '$GATK_HOME/GenomeAnalysisTK.jar'

def java_command(jar_path, mem_in_gb, command_args):
    '''Build a string for running a java command'''
    # Bit of room between Java's max heap memory and what was requested.
    # Allows for other Java memory usage, such as stack.
    java_mem = mem_in_gb - 2
    return 'java -Xmx{mem}g -jar {jar_path} {command_args}'.format(
        jar_path=jar_path, mem=java_mem, command_args=command_args)


def run_java(state, stage, jar_path, mem, args):
    command = java_command(jar_path, mem, args)
    run_stage(state, stage, command)


class Stages(object):
    def __init__(self, state):
        self.state = state
        self.reference = self.get_options('ref_grch37')
        self.dbsnp_grch37 = self.get_options('dbsnp_grch37')
        self.mills_grch37 = self.get_options('mills_grch37')
        self.one_k_g_grch37_indels = self.get_options('one_k_g_grch37_indels')
        self.one_k_g_snps = self.get_options('one_k_g_snps')
        self.one_k_g_indels = self.get_options('one_k_g_indels')
        self.one_k_g_highconf_snps = self.get_options('one_k_g_highconf_snps')
        self.hapmap = self.get_options('hapmap')
        self.interval_grch37 = self.get_options('interval_grch37')
        self.CEU_mergeGvcf = self.get_options('CEU_mergeGvcf')
        self.GBR_mergeGvcf = self.get_options('GBR_mergeGvcf')
        self.FIN_mergeGvcf = self.get_options('FIN_mergeGvcf')

    def run_picard(self, stage, args):
        mem = int(self.state.config.get_stage_options(stage, 'mem'))
        return run_java(self.state, stage, PICARD_JAR, mem, args)

    def run_gatk(self, stage, args):
        mem = int(self.state.config.get_stage_options(stage, 'mem'))
        return run_java(self.state, stage, GATK_JAR, mem, args)


    def get_stage_options(self, stage, *options):
        return self.state.config.get_stage_options(stage, *options)

    def get_options(self, *options):
        return self.state.config.get_options(*options)


    def original_fastqs(self, output):
        '''Original fastq files'''
        pass


    def align_bwa(self, inputs, bam_out, sample_id):
        '''Align the paired end fastq files to the reference genome using bwa'''
        fastq_read1_in, fastq_read2_in = inputs
        cores = self.get_stage_options('align_bwa', 'cores')
        read_group = '"@RG\tID:{sample}\tSM:{sample}\tPL:Illumina"'.format(sample=sample_id)
        command = 'bwa mem -t {cores} -R {read_group} {reference} {fastq_read1} {fastq_read2} ' \
                  '| samtools view -b -h -o {bam} -' \
                  .format(cores=cores,
                      read_group=read_group,
                      fastq_read1=fastq_read1_in,
                      fastq_read2=fastq_read2_in,
                      reference=self.reference,
                      bam=bam_out)
        run_stage(self.state, 'align_bwa', command)


    def sort_bam_picard(self, bam_in, sorted_bam_out):
        '''Sort the BAM file using Picard'''
        picard_args = 'SortSam INPUT={bam_in} OUTPUT={sorted_bam_out} ' \
                      'VALIDATION_STRINGENCY=LENIENT SORT_ORDER=coordinate ' \
                      'MAX_RECORDS_IN_RAM=5000000 CREATE_INDEX=True'.format(
                          bam_in=bam_in, sorted_bam_out=sorted_bam_out)
        self.run_picard('sort_bam_picard', picard_args)


    def mark_duplicates_picard(self, bam_in, outputs):
        '''Mark duplicate reads using Picard'''
        dedup_bam_out, metrics_out = outputs
        picard_args = 'MarkDuplicates INPUT={bam_in} OUTPUT={dedup_bam_out} ' \
                      'METRICS_FILE={metrics_out} VALIDATION_STRINGENCY=LENIENT ' \
                      'MAX_RECORDS_IN_RAM=5000000 ASSUME_SORTED=True ' \
                      'CREATE_INDEX=True'.format(bam_in=bam_in, dedup_bam_out=dedup_bam_out,
                          metrics_out=metrics_out)
        self.run_picard('mark_duplicates_picard', picard_args)


    def chrom_intervals_gatk(self, inputs, intervals_out):
        '''Generate chromosome intervals using GATK'''
        bam_in, _metrics_dup = inputs
        cores = self.get_stage_options('chrom_intervals_gatk', 'cores')
        gatk_args = '-T RealignerTargetCreator -R {reference} -I {bam} ' \
                    '--num_threads {threads} --known {mills_grch37} ' \
                    '--known {one_k_g_grch37_indels} -L {interval_grch37} ' \
                    '-o {out}'.format(reference=self.reference, bam=bam_in,
                            threads=cores, mills_grch37=self.mills_grch37,
                            one_k_g_grch37_indels=self.one_k_g_grch37_indels,
                            interval_grch37=self.interval_grch37,
                            out=intervals_out)
        self.run_gatk('chrom_intervals_gatk', gatk_args)


    def local_realignment_gatk(self, inputs, bam_out):
        '''Local realign reads using GATK'''
        target_intervals_in, bam_in = inputs
        gatk_args = "-T IndelRealigner -R {reference} -I {bam} -L {interval_grch37} " \
                    "-targetIntervals {target_intervals} -known {mills_grch37} " \
                    "-known {one_k_g_grch37_indels} " \
                    "-o {out}".format(reference=self.reference, bam=bam_in,
                            mills_grch37=self.mills_grch37,
                            one_k_g_grch37_indels=self.one_k_g_grch37_indels,
                            interval_grch37=self.interval_grch37,
                            target_intervals=target_intervals_in,
                            out=bam_out)
        self.run_gatk('local_realignment_gatk', gatk_args)


    # XXX I'm not sure that --num_cpu_threads_per_data_thread has any benefit here
    def base_recalibration_gatk(self, bam_in, outputs):
        '''Base recalibration using GATK'''
        csv_out, log_out = outputs
        gatk_args = "-T BaseRecalibrator -R {reference} -I {bam} " \
                    "--num_cpu_threads_per_data_thread 4 --knownSites {dbsnp_grch37} " \
                    "--knownSites {mills_grch37} --knownSites {one_k_g_grch37_indels} " \
                    "-log {log} -o {out}".format(reference=self.reference, bam=bam_in,
                            mills_grch37=self.mills_grch37, dbsnp_grch37=self.dbsnp_grch37,
                            one_k_g_grch37_indels=self.one_k_g_grch37_indels,
                            log=log_out, out=csv_out)
        self.run_gatk('base_recalibration_gatk', gatk_args)


    # XXX I'm not sure that --num_cpu_threads_per_data_thread has any benefit here
    def print_reads_gatk(self, inputs, bam_out):
        '''Print reads using GATK'''
        [csv_in, _log], bam_in = inputs
        gatk_args = "-T PrintReads -R {reference} -I {bam} --BQSR {recal_csv} " \
                    "-o {out} --num_cpu_threads_per_data_thread 4".format(reference=self.reference,
                            bam=bam_in, recal_csv=csv_in, out=bam_out)
        self.run_gatk('print_reads_gatk', gatk_args)


    def call_variants_gatk(self, bam_in, vcf_out):
        '''Call variants using GATK'''
        gatk_args = "-T HaplotypeCaller -R {reference} --min_base_quality_score 20 " \
                    "--variant_index_parameter 128000 --emitRefConfidence GVCF " \
                    "--standard_min_confidence_threshold_for_calling 30.0 " \
                    "--num_cpu_threads_per_data_thread 8 " \
                    "--variant_index_type LINEAR " \
                    "--standard_min_confidence_threshold_for_emitting 30.0 " \
                    "-I {bam} -L {interval_list} -o {out}".format(reference=self.reference,
                            bam=bam_in, interval_list=self.interval_grch37, out=vcf_out)
        self.run_gatk('call_variants_gatk', gatk_args)


    def combine_gvcf_gatk(self, vcf_files_in, vcf_out):
        '''Combine G.VCF files for all samples using GATK'''
        g_vcf_files = ' '.join(['--variant ' + vcf for vcf in vcf_files_in])
        gatk_args = "-T CombineGVCFs -R {reference} " \
                    "--disable_auto_index_creation_and_locking_when_reading_rods " \
                    "{g_vcf_files} -o {vcf_out}".format(reference=self.reference,
                        g_vcf_files=g_vcf_files, vcf_out=vcf_out)
        self.run_gatk('combine_gvcf_gatk', gatk_args)


    def genotype_gvcf_gatk(self, merged_vcf_in, vcf_out):
        '''Genotype G.VCF files using GATK'''
        cores = self.get_stage_options('genotype_gvcf_gatk', 'cores')
        gatk_args = "-T GenotypeGVCFs -R {reference} " \
                    "--disable_auto_index_creation_and_locking_when_reading_rods " \
                    "--num_threads {cores} --variant {merged_vcf} --out {vcf_out} " \
                    "--variant {CEU_mergeGvcf} --variant {GBR_mergeGvcf} " \
                    "--variant {FIN_mergeGvcf}".format(reference=self.reference,
                            cores=cores, merged_vcf=merged_vcf_in, vcf_out=vcf_out,
                            CEU_mergeGvcf=self.CEU_mergeGvcf, GBR_mergeGvcf=self.GBR_mergeGvcf,
                            FIN_mergeGvcf=self.FIN_mergeGvcf)
        self.run_gatk('genotype_gvcf_gatk', gatk_args)


    def snp_recalibrate_gatk(self, genotype_vcf_in, outputs):
        '''SNP recalibration using GATK'''
        recal_snp_out, tranches_snp_out, snp_plots_r_out = outputs
        cores = self.get_stage_options('snp_recalibrate_gatk', 'cores')
        gatk_args = "-T VariantRecalibrator --disable_auto_index_creation_and_locking_when_reading_rods " \
                    "-R {reference} --minNumBadVariants 5000 --num_threads {cores} " \
                    "-resource:hapmap,known=false,training=true,truth=true,prior=15.0 {hapmap} " \
                    "-resource:omni,known=false,training=true,truth=true,prior=12.0 {one_k_g_snps} " \
                    "-resource:1000G,known=false,training=true,truth=false,prior=10.0 {one_k_g_highconf_snps} " \
                    "-an QD -an MQRankSum -an ReadPosRankSum -an FS -an InbreedingCoeff " \
                    "-input {genotype_vcf} --recal_file {recal_snp} --tranches_file {tranches_snp} " \
                    "-rscriptFile {snp_plots} -mode SNP".format(reference=self.reference,
                            cores=cores, hapmap=self.hapmap, one_k_g_snps=self.one_k_g_snps,
                            one_k_g_highconf_snps=self.one_k_g_highconf_snps, genotype_vcf=genotype_vcf_in,
                            recal_snp=recal_snp_out, tranches_snp=tranches_snp_out, snp_plots=snp_plots_r_out)
        self.run_gatk('snp_recalibrate_gatk', gatk_args)


    def indel_recalibrate_gatk(self, genotype_vcf_in, outputs):
        '''INDEL recalibration using GATK'''
        recal_indel_out, tranches_indel_out, indel_plots_r_out = outputs
        cores = self.get_stage_options('indel_recalibrate_gatk', 'cores')
        gatk_args = "-T VariantRecalibrator --disable_auto_index_creation_and_locking_when_reading_rods " \
                    "-R {reference} --minNumBadVariants 5000 --num_threads {cores} " \
                    "-resource:mills,known=false,training=true,truth=true,prior=12.0 {mills_grch37} " \
                    "-resource:1000G,known=false,training=true,truth=true,prior=10.0 {one_k_g_indels} " \
                    "-an MQRankSum -an ReadPosRankSum -an FS -input {genotype_vcf} -recalFile {recal_indel} " \
                    "-tranchesFile {tranches_indel} -rscriptFile {indel_plots} " \
                    " -mode INDEL".format(reference=self.reference,
                            cores=cores, mills_grch37=self.mills_grch37, one_k_g_indels=self.one_k_g_indels,
                            genotype_vcf=genotype_vcf_in, recal_indel=recal_indel_out,
                            tranches_indel=tranches_indel_out, indel_plots=indel_plots_r_out)
        self.run_gatk('indel_recalibrate_gatk', gatk_args)


    def apply_snp_recalibrate_gatk(self, inputs, vcf_out):
        '''Apply SNP recalibration using GATK'''
        genotype_vcf_in, [recal_snp, tranches_snp] = inputs 
        cores = self.get_stage_options('apply_snp_recalibrate_gatk', 'cores')
        gatk_args = "-T ApplyRecalibration --disable_auto_index_creation_and_locking_when_reading_rods " \
                    "-R {reference} --ts_filter_level 99.5 --excludeFiltered --num_threads {cores} " \
                    "-input {genotype_vcf} -recalFile {recal_snp} -tranchesFile {tranches_snp} " \
                    "-mode SNP -o {vcf_out}".format(reference=self.reference,
                            cores=cores, genotype_vcf=genotype_vcf_in, recal_snp=recal_snp,
                            tranches_snp=tranches_snp, vcf_out=vcf_out)
        self.run_gatk('apply_snp_recalibrate_gatk', gatk_args)


    def apply_indel_recalibrate_gatk(self, inputs, vcf_out):
        '''Apply INDEL recalibration using GATK'''
        genotype_vcf_in, [recal_indel, tranches_indel] = inputs 
        cores = self.get_stage_options('apply_indel_recalibrate_gatk', 'cores')
        gatk_args = "-T ApplyRecalibration --disable_auto_index_creation_and_locking_when_reading_rods " \
                    "-R {reference} --ts_filter_level 99.0 --excludeFiltered --num_threads {cores} " \
                    "-input {genotype_vcf} -recalFile {recal_indel} -tranchesFile {tranches_indel} " \
                    "-mode INDEL -o {vcf_out}".format(reference=self.reference,
                            cores=cores, genotype_vcf=genotype_vcf_in, recal_indel=recal_indel,
                            tranches_indel=tranches_indel, vcf_out=vcf_out)
        self.run_gatk('apply_indel_recalibrate_gatk', gatk_args)


    def combine_variants_gatk(self, inputs, vcf_out):
        '''Combine variants using GATK'''
        recal_snp, [recal_indel] = inputs 
        cores = self.get_stage_options('combine_variants_gatk', 'cores')
        gatk_args = "-T CombineVariants -R {reference} --disable_auto_index_creation_and_locking_when_reading_rods " \
                    "--num_threads {cores} --genotypemergeoption UNSORTED --variant {recal_snp} " \
                    "--variant {recal_indel} -o {vcf_out}".format(reference=self.reference,
                            cores=cores, recal_snp=recal_snp, recal_indel=recal_indel,
                            vcf_out=vcf_out)
        self.run_gatk('combine_variants_gatk', gatk_args)


    def select_variants_gatk(self, combined_vcf, vcf_out):
        '''Select variants using GATK'''
        gatk_args = "-T SelectVariants -R {reference} --disable_auto_index_creation_and_locking_when_reading_rods " \
                    "--variant {combined_vcf} -select 'DP > 100' -o {vcf_out}".format(reference=self.reference,
                            combined_vcf=combined_vcf, vcf_out=vcf_out)
        self.run_gatk('select_variants_gatk', gatk_args)
