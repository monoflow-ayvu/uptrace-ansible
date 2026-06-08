{ pkgs, lib, config, inputs, ... }:

{
  packages = with pkgs; [
    git
    flyctl
    ansible
  ];

  # See full reference at https://devenv.sh/reference/options/
}
