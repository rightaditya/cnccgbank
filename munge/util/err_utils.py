import sys
import time

def stream_report(stream, preface, msg, *fmts):
    print >> stream, "%s: %s" % (preface, (msg % fmts))
    
def warn(msg, *fmts):
    stream_report(sys.stderr, "warning", msg, *fmts)
    
def info(msg, *fmts):
    stream_report(sys.stderr, "info", msg, *fmts)
    
def debug(msg, *fmts):
    stream_report(sys.stderr, time.asctime(), msg, *fmts)