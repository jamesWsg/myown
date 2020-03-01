#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging.config


__all__ = ['logger']

formatter = '[%(asctime)s] [%(levelname)s] [%(process)d] [%(module)s.%(funcName)s] %(message)s'
simple_formatter = '[%(asctime)s] [%(levelname)s] [%(module)s.%(funcName)s] %(message)s'
logging.config.dictConfig({
    'version': 1,
    'formatters': {
        'standard': {
            'format': formatter
        },
        'simple': {
            'format': simple_formatter
        }
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'formatter': 'standard',
            'filename': 's3_benchmark.log',
            'mode': 'w',
            'encoding': 'utf-8'
        },
        'report': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'formatter': 'simple',
            'filename': 'report.log',
            'mode': 'w',
            'encoding': 'utf-8'
        },
    },
    'loggers': {
        's3_benchmark': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True
        }
    }
})
logger = logging.getLogger('s3_benchmark')
