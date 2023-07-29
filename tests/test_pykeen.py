from dicee.executer import Execute
import sys
import pytest
from dicee.config import Namespace as Args


def template(model_name):
    args = Args()
    args.path_dataset_folder = "KGs/UMLS"
    args.trainer = "torchCPUTrainer"
    args.model = model_name
    args.num_epochs = 10
    args.batch_size = 256
    args.lr = 0.1
    args.num_workers = 1
    args.num_core = 1
    args.scoring_technique = "KvsAll"
    args.num_epochs = 10
    args.pykeen_model_kwargs = {"embedding_dim": 64}
    args.sample_triples_ratio = None
    args.read_only_few = None
    args.num_folds_for_cv = None
    return args



@pytest.mark.parametrize("model_name", 
  ["Pykeen_DistMult",
    "Pykeen_ComplEx",
    "Pykeen_QuatE",
    "Pykeen_MuRE",])
class TestClass:
    def test_defaultParameters_case(self, model_name):
        args = template(model_name)
        result = Execute(args).start()
        if args.model == "Pykeen_DistMult":
            assert 0.84 >= result["Train"]["MRR"] >= 0.800
        elif args.model == "Pykeen_ComplEx":
            assert 0.92 >= result["Train"]["MRR"] >= 0.88
        elif args.model == "Pykeen_QuatE":
            assert 0.999 >= result["Train"]["MRR"] >= 0.94
        elif args.model == "Pykeen_MuRE":
            assert 0.88 >= result["Train"]["MRR"] >= 0.82

    def test_GNCallback_case(self, model_name):
        args = template(model_name)
        args.callbacks = {'GN':{"std":0.1}}
        Execute(args).start()
       
        
        
        
    
