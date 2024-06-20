#!/bin/bash

DIR_EXPORT="/home/lucile/eXamc/rooms_plans/export"
DIR_CSV="/home/lucile/eXamc/rooms_plans/csv_special_numbers"

if [ -d "$DIR_EXPORT" ] || [ -d "$DIR_CSV" ]; then

  rm -rf "$DIR_EXPORT"/*
  rm -rf "$DIR_CSV"/*
else
  if [ ! -d "$DIR_EXPORT" ]; then
    echo "Directory: $DIR_EXPORT doesn't exist."
  fi
  if [ ! -d "$DIR_CSV" ]; then
    echo "Directory: $DIR_CSV doesn't exist."
  fi
fi
