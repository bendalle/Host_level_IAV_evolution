
# coding: utf-8

# # Investigating mixed infections
# 
# _Note because of the reliance on our variant_pipeline repository this analysis runs in python 2.7._
# 
# There are some samples that appear to be mixed infections. These contain >10 iSNV all with very similar frequencies. My plan here is to introduce those iSNV to the sample consensus sequence and then compare both the major and minor haplotypes with strains that were circulating during the past few years.
# 
# 
# The samples we are interested in are ["HS1530" "M54062" "MH8125" "MH8137" "MH8156" "MH8390"]
# The plan
#     - read in iSNV
#     - incorporate iSNV into consensus sequence - This will draw heavily from what we do in the pipeline when we classify variants in the script AA_var.py
#     - Compare both haplotypes to the plasmid controls we have for all seasons.
#     
#     

# In[1]:


import numpy as np
import pandas as pd
import copy 
from matplotlib import pyplot as plt
import os
import tempfile
import sys
import subprocess
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio import SeqIO
from Bio.Alphabet import IUPAC
from Bio import Phylo
from ast import literal_eval

import re
get_ipython().run_line_magic('matplotlib', 'inline')



# ## Read in iSNV

# In[2]:


qual = pd.read_csv("../data/processed/secondary/qual.snv.csv")
#meta = pd.read_csv("../data/reference/all_meta.sequence_success.csv")
samples_of_interest = ["HS1530","M54062","MH8125", "MH8137", "MH8156" ,"MH8390"]
interesting = qual.loc[(qual.SPECID.isin(samples_of_interest))]


# In[3]:


interesting


# ## Incorporate iSNV into the consensus sequences 
# 
# These functions are used to incorporate the isnv in the data frame into the consensus sequences parsed by deepSNV. A discription of each function is included below.
# 

# In[4]:


sys.path.append("/Users/jt/lauring_lab_repos/variant_pipeline/scripts/")
from fasta_functions import StripGapsToFirstSequence, Align

        
def ReadFASTA(fastafile):
    """Reads sequences from a FASTA file.

    'fastafile' should specify the name of a FASTA file.

    This function reads all sequences from the FASTA file.  It returns the
        list 'headers_seqs'.  This list is composed of a seq_record objects.
    """
    seqs =[]
    header = None
    for seq_record in SeqIO.parse(fastafile, "fasta"):
        seq_record.seq.alphabet=IUPAC.unambiguous_dna
        seqs.append(seq_record)

    return seqs



def mutate(sequence,variants_df):
    """ This function takes in a Seq object and a data frame with mutations with chr, pos, ref, var columns. It 
    applies the mutations and then returns a sequence containing all the mutations in the variant data frame.
    """
    seq=copy.deepcopy(sequence)
    seq.seq=seq.seq.tomutable()
    
    # Get the most recent coding position 
    df=variants_df
    for index, row in df.iterrows():
        #if row["ref"]!=seq.seq[int(row["pos"])-1]:
        #    raise ValueError("Reference base does not match the reference base in the sequence")
        seq.seq[int(row["pos"])-1]=row["var"]
    seq.seq=seq.seq.toseq()
    return seq    


def trim_to_coding(fasta,SPECID,meta):
    """This funciton trims a sample fasta sequence to the reading frame defined in a separate fasta file
    First the funciton takes in the SPECID and looks up where the sample fasta file will be using the meta data
    available in the meta argument. For each sequence in the reference the function looks for the same sequence name
    in the sample fasta. It then alings this and trims the gaps so we are left with just the OR."""
    
    samp_meta = get_meta(SPECID,meta)
    
    regions = run_to_OR(samp_meta["run"])
    
    coding = ReadFASTA(regions)
    # cycle through fasta 
    OR=[]
    for gene in fasta:
        seg_id=gene.id  
        gene.description = "this is the test sample" + gene.description
        for code in coding:
            code_id = code.id
            if seg_id ==code_id:
                #print('working with %s' %seg_id) #and seg_id=="NR":
                code_gene=Align([code,gene],"/Users/jt/muscle3.8.31/")
                code_gene_trimmed = StripGapsToFirstSequence(code_gene)
                OR.append(code_gene_trimmed)
        
    return(OR)

def get_haplotype(data,fasta,min_freq,max_freq):
    """This function takes in a data frame containing isnv calls, it filters to include only those
    isnv between the frequency thresholds provided. It then applies these mutations to the fasta file. Note
    The position in the data frame is base 1 - This is taken into account in the mutate function. Also,
    The fasta sequences can not be trimmed prior to this process. If they are the position in the data frame
    will not correspond to those in the fasta sequence."""
    isnv = copy.deepcopy(data.loc[(data["freq.var"]>min_freq) & (data["freq.var"]<max_freq) ])
    consensus =  ReadFASTA(fasta)
    # cycle through segments and apply iSNV
    hap = []
    #print(isnv)
    for ref in consensus:
        seg = ref.id
        seg_var = isnv.loc[isnv["chr"]==seg]
        
        seg_isnv = mutate(ref,seg_var)
        
        seg_isnv.name = isnv.SPECID.unique()[0]+"_isnv"
     #   print(isnv.SPECID.unique())
        hap.append(seg_isnv)
    return(hap)

def get_meta(SPECID,meta):
    """This function takes a SPECID and data frame with meta data and
    returns a dictionary of the meta data for that sample."""
    ID = meta.loc[meta.SPECID==SPECID,"Id"].unique()[0]
    ID = ID.split(".")[0]
    RUN = meta.loc[meta.SPECID==SPECID,"run"].unique()[0]
    season = meta.loc[meta.SPECID==SPECID,"season"].unique()[0]
    ENROLLID = meta.loc[meta.SPECID==SPECID,"ENROLLID"].unique()[0]
    HOUSE_ID = meta.loc[meta.SPECID==SPECID,"HOUSE_ID"].unique()[0]
    if RUN=="vic":
        RUN="victoria"
    if RUN=="vic_2":
        RUN="victoria_2"
    return({"Id":ID,"run":RUN,"season":season,"enrollid":ENROLLID,"house_id":HOUSE_ID})

def run_to_OR(run):
    
    """This function takes in the name of sequencing run from this study and returns the relative path
    to the fasta files with the OR for that sample."""
    conversion={"perth":"../data/reference/perth.OR.main.fa",
               "perth_2": "../data/reference/perth.OR.main.fa",
               "cali09":"../data/reference/cali09.OR.main.fa",
               "cali09_2":"../data/reference/cali09.OR.main.fa",
               "victoria":"../data/reference/victoria.OR.main.fa",
               "victoria_2":"../data/reference/victoria.OR.main.fa",
               "HK_1":"../data/reference/NY.OR.main.fa",
               "HK_2":"../data/reference/NY.OR.main.fa",
               "HK_6":"../data/reference/NY.OR.main.fa",
               "HK_7":"../data/reference/NY.OR.main.fa",
               "HK_8":"../data/reference/NY.OR.main.fa"}
    return(conversion[run])


# These functions are used to cycle through lists of SPECID and return haplotypes with minority variants incorporated or simply the consensus sequences. In both cases the sequences are trimmed to the coding regions.

# In[5]:


def get_isnv_seq(specid_list,snv_data,meta_run):
    """This function takes a list of SPECIDs, a data frame of isnv calls for those samples and 
    data frame with meta data for the samples. For each SPECID we get the meta data in dictionary form,
    Get the consensus fasta file, apply the minority mutations to the fasta file, Trim the new sequences to 
    the coding regions and return a dictionary of the results indexed by SPECID."""
    sequences = {}
    for specid in specid_list:
        meta = get_meta(specid,meta_run)
        fa = "../data/processed/"+meta["run"]+"/parsed_fa/"+meta["Id"]+".removed.parsed.fasta"
        haplo_sequence = get_haplotype(data= snv_data.loc[snv_data.SPECID==specid],fasta =fa,min_freq=0.02,max_freq = 0.5)
        
        haplo_coding = trim_to_coding(haplo_sequence,specid,meta_run)
        specid_key = '%s_%s_%s_%s_minor' % (specid,meta["enrollid"],meta["house_id"],meta["season"])
        
        sequences[specid_key] = haplo_coding
    
    return(sequences)


def get_seq(specid_list,meta_run):
    """This function takes a list of SPECIDs and data frame with meta data for the samples. It is similar to the 
    function above but it does not add isnv to the sequences. It only returns the consensus sequences.
    For each SPECID we get the meta data in dictionary form,g et the consensus fasta file, 
    Trim the new sequences to the coding regions and return a dictionary of the results indexed by SPECID."""
    sequences={}
    for specid in specid_list:
        meta = get_meta(specid,meta_run)
        fa = "../data/processed/"+meta["run"]+"/parsed_fa/"+meta["Id"]+".removed.parsed.fasta"
        seq = ReadFASTA(fa)
    
        for seg in seq:
            seg.name=specid
        
        seg_coding = trim_to_coding(seq,specid,meta_run)
        specid_key = '%s_%s_%s_%s_consensus' % (specid,meta["enrollid"],meta["house_id"],meta["season"])
        sequences[specid_key] = seg_coding 
    return(sequences)


#sequences


# ## Interesting samples - minor haplotypes
# 
# Here we get the minor and conensus haplotypes of the putative mixed infections.

# In[6]:


interesting_haplotypes = get_isnv_seq(specid_list=samples_of_interest,snv_data=qual,meta_run=qual)
major_haplotypes = get_seq(specid_list=samples_of_interest,meta_run=qual)
interesting_haplotypes.update(major_haplotypes)


# In[7]:


interesting_haplotypes.keys()
#major_haplotypes.keys()


# ## All other samples
# 
# I'm looking at H3N2 and H1N1 samples separately

# In[8]:


H3N2_samples = qual.loc[qual.pcr_result == "A/H3N2", "SPECID"].unique()
H3N2_samples = [x for x in H3N2_samples if x not in interesting_haplotypes.keys()]
H3N2_seq = get_seq(specid_list=H3N2_samples,meta_run=qual)


# In[9]:


H1N1_samples = qual.loc[qual.pcr_result == "A/H1N1", "SPECID"].unique()
H1N1_samples = [x for x in H1N1_samples if x not in interesting_haplotypes.keys()]


H1N1_seq = get_seq(specid_list=H1N1_samples,meta_run=qual)


# ## Control files
# 
# To add the control files we'll make dictionaries to mimic those used in the patient isolates.

# In[10]:


control_files = {"Victoria":"../data/processed/victoria/parsed_fa/Vic_pool.removed.parsed.fasta",
                "Perth" : "../data/processed/perth/parsed_fa/Perth_mp.removed.parsed.fasta",
                "HK":"../data/processed/HK_1/parsed_fa/PC1A.removed.parsed.fasta",
                "H1N1": "../data/processed/cali09/parsed_fa/Cali_pool.removed.parsed.fasta"}
control_meta = {'SPECID': ["Victoria","Perth","HK","H1N1"],
     'Id': ["Victoria","Perth","HK","H1N1"],
     'run':["victoria","perth","HK_1","cali09"],
    'season':["12-13","10-12","2014-2015","10-15"],
    'ENROLLID':["PC","PC","PC","PC"],
    'HOUSE_ID':["PC","PC","PC","PC"]}
control_meta = pd.DataFrame(data=control_meta, index=None)
control_seq={}
for key in control_files:
    seq = ReadFASTA(control_files[key])
    for seg in seq:
        seg.name = key
    seg_coding = trim_to_coding(seq,key,control_meta)
    control_seq[key] = seg_coding 

#control_seq


# Now we will get the out group ready. This has been trimmed to the coding regions. It is A/Wisconsin/67/2005(H3N2)

# In[13]:


out_group = ReadFASTA("../data/reference/wisconsin.OR.fa")
out_group_d = {"Wisconsin_2005":out_group}


# I will include the samples of interest and the controls in each tree comparision.

# In[14]:


H3N2_seq.update(interesting_haplotypes)
H3N2_seq.update(control_seq)
H3N2_seq.update(out_group_d)

H1N1_seq.update(interesting_haplotypes)
H1N1_seq.update(control_seq)


# ## Making trees
# 
# This uses muscle to align segments and then fasttree to make a tree.

# In[15]:


def make_alignments(seg,sequences,out_dir,out_file):
    """ This function aligns the sequences provided using muscle. The input is a list of dictionaries of 
    sequences. The segment of interest is provided as the seg argument.
    """
    
    segment = []
    for sample in sequences:
        for chrom in sequences[sample]:
            if chrom.id==seg:
                seg_copy = copy.deepcopy(chrom)
                seg_copy.id = seg_copy.name
                segment.append(seg_copy)
    
    muscle_progpath = "/Users/jt/muscle3.8.31"
    muscle_exe = os.path.abspath("%s/muscle" % muscle_progpath) # the executable
    
    
    currdir = os.getcwd()
    # make directory if it doesn't exist.
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    
    infile_fa = "%s/in.fasta" % out_dir # input file
    align_fa = "%s/%s" % (out_dir,out_file) # output file
    
   
    print("Writing %d sequences to file" % len(segment))
    
    SeqIO.write(segment, infile_fa, "fasta") # write sequences to the input file
    
    print("%s\n %s -in %s -out %s" % ("Making alignment",muscle_exe, infile_fa, align_fa))
    
    p = subprocess.Popen("%s -in %s -out %s" % (muscle_exe, infile_fa, align_fa), shell = True, stdout = subprocess.PIPE, stderr = subprocess.PIPE) # run MUSCLE
    (output, errors) = p.communicate()
    
    

def make_tree(in_fasta,tree_file):
    # Make the tree
    """This function uses fasttree to make a ML tree of the sequences present in an aligned fasta file"""
    tree_progpath = "/Users/jt"
    tree_exe = os.path.abspath("%s/FastTree" % tree_progpath) # the executable
    #tree_file = "%s/tree.file" % tempdir
    print(" %s \n %s -nt %s > %s" % ("Making tree:",tree_exe, in_fasta,tree_file))
    
    t = subprocess.Popen("%s -nt %s > %s" % (tree_exe, in_fasta,tree_file), shell = True, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    (output, errors) = t.communicate()

    


# ## H3N2 Concatenated tree
# 
# There are no H1N1 H3N2 mixed infections so each tree is just H3N2 or H1N1 for visualization purposes.
# 
# 

# In[16]:


def concat_seqs(sequences):
    """This funciton concatenates sequences present in a dictionary of sequences."""
    concat_seq={}
    for key in sequences:
        str_seq = "".join([str(seq_rec.seq) for seq_rec in sequences[key]])
        concat_seq[key]= [SeqRecord( Seq(str_seq),id="All",name=key)]# needs to be list to match function above
    return(concat_seq)


# In[17]:


H3N2_concat_seq = concat_seqs(H3N2_seq)
H3N2_concat_seq.keys()


# In[18]:



H1N1_hideaways = ["H1N1","M54062","M54062_isnv"]

for extra in H1N1_hideaways:
    for k in H3N2_concat_seq.keys():
        if extra in k:
            H3N2_concat_seq.pop(k)
            print "removed %s" % k


# Make the alignment file

# In[19]:


make_alignments(seg="All",sequences=H3N2_concat_seq,out_dir="./coding_alignments",out_file="H3N2_coding.fa")



# Make the tree file

# In[20]:


make_tree("./coding_alignments/H3N2_coding.fa","./coding_alignments/H3N2_coding.tree")


# Make the annotation file

# In[21]:


with open("./coding_alignments/H3N2.annotations.tsv","w") as a:
    a.write("taxa\tSPECID\tENROLLID\tHOUSE_ID\tseason\tclass\n")
    for samp in H3N2_concat_seq.keys():
        
        annotations = samp.split("_")
        while len(annotations)<5:
                    annotations.append("PC")
        #print(annotations)
        line = "%s\t%s\t%s\t%s\t%s\t%s\n" % (samp,annotations[0],annotations[1],annotations[2],annotations[3],annotations[4])
        a.write(line)


# ## H1N1 Concatenated tree
# 
# First we add the out group Calidonia 99 and the concatenate and make the tree

# In[22]:


out_group_H1 = ReadFASTA("../data/reference/calidonia99.OR.fa")
out_group_H1_d = {"Calidonia_99":out_group_H1}
H1N1_seq.update(out_group_H1_d)
H1N1_concat_seq = concat_seqs(H1N1_seq)
H3N2_hideaways = ["HK","HS1530","HS1530_isnv","MH8137","MH8137_isnv","MH8390","MH8390_isnv","Victoria","Perth","MH8156","MH8156_isnv","MH8125","MH8125_isnv"]

for extra in H3N2_hideaways:
    for k in H1N1_concat_seq.keys():
        if extra in k:
            H1N1_concat_seq.pop(k)
            print "removed %s" % k




# In[23]:


make_alignments(seg="All",sequences=H1N1_concat_seq,out_dir="./coding_alignments",out_file="H1N1_coding.fa")


# In[24]:


make_tree("./coding_alignments/H1N1_coding.fa","./coding_alignments/H1N1_coding.tree")


# In[25]:


with open("./coding_alignments/H1N1.annotations.tsv",'w') as a:
    a.write("taxa\tSPECID\tENROLLID\tHOUSE_ID\tseason\tclass\n")
    for samp in H1N1_concat_seq.keys():
        annotations = samp.split("_")
        while len(annotations)<5:
                    annotations.append("PC")
        line = "%s\t%s\t%s\t%s\t%s\t%s\n" % (samp,annotations[0],annotations[1],annotations[2],annotations[3],annotations[4])
        a.write(line)


# In[43]:


len(H3N2_concat_seq["HK"][0].seq)

